# your_app/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from typing import Optional
from ride_matching.models import Booking
from LocationSystem.socket_contract import (
    SocketEventType,
    TripState,
    build_envelope,
    can_stream_location,
)


STATUS_TO_TRIP_STATE = {
    "confirmed": TripState.EN_ROUTE_TO_PICKUP.value,
    "active": TripState.EN_ROUTE_TO_PICKUP.value,
    "arrived": TripState.ARRIVED.value,
    "completed": TripState.COMPLETED.value,
    "cancelled": TripState.CANCELLED.value,
}


@database_sync_to_async
def get_booking_stream_context(trip_id, socket_driver_id, scope_user_id=None):
    booking = (
        Booking.objects.select_related("bus__driver__user")
        .filter(id=trip_id)
        .first()
    )
    if not booking:
        return None, None, "trip_not_found"

    assigned_driver_profile = booking.bus.driver
    allowed_socket_ids = {
        str(assigned_driver_profile.id),
        str(assigned_driver_profile.user_id),
    }
    if str(socket_driver_id) not in allowed_socket_ids:
        return None, None, "driver_trip_mismatch"

    if scope_user_id and assigned_driver_profile.user_id != scope_user_id:
        return None, None, "unauthorized_driver_socket"

    raw_state = getattr(booking, "trip_state", None) or booking.status
    normalized_state = STATUS_TO_TRIP_STATE.get(str(raw_state).lower(), str(raw_state))
    return booking.id, normalized_state, None


class DriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driver_id = self.scope['url_route']['kwargs']['driver_id']
        self.room_group_name = f"driver_{self.driver_id}"

        # Join group for this driver
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming websocket messages from the driver client.
        Expect JSON payloads. A simple, extensible pattern:
        {
            "action": "location" | "status" | "heartbeat" | "exchange_token" | ...,
            "data": { ... }
        }
        """
        # Parse incoming text JSON safely
        if text_data is None:
            # If you're not using binary frames, ignore bytes_data for now
            return

        try:
            message = json.loads(text_data)
        except json.JSONDecodeError:
            # send error back to client (or silently ignore)
            await self.send(text_data=json.dumps({
                "error": "invalid_json",
                "detail": "Could not decode JSON"
            }))
            return

        action: Optional[str] = message.get("action")
        data = message.get("data", {})

        # Basic routing by action type - extend as needed
        if action == "location":
            trip_id = data.get("trip_id")
            user = self.scope.get("user")
            scope_user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
            actor_role = "driver"

            resolved_trip_id, trip_state, context_error = await get_booking_stream_context(
                trip_id=trip_id,
                socket_driver_id=self.driver_id,
                scope_user_id=scope_user_id,
            )
            if context_error:
                await self.send(text_data=json.dumps({
                    "error": context_error,
                    "detail": "Could not authorize this trip stream",
                }))
                return

            if not can_stream_location(actor_role=actor_role, trip_state=trip_state):
                await self.send(text_data=json.dumps({
                    "error": "stream_not_allowed",
                    "detail": (
                        "Location streaming is only allowed for drivers in "
                        f"{TripState.EN_ROUTE_TO_PICKUP.value}"
                    ),
                }))
                return

            try:
                location_event = build_envelope(
                    event_type=SocketEventType.LOCATION_UPDATE.value,
                    trip_id=resolved_trip_id,
                    payload=data.get("payload", {}),
                )
            except ValueError as exc:
                await self.send(text_data=json.dumps({
                    "error": "invalid_event",
                    "detail": str(exc),
                }))
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "driver_update",   # maps to driver_update() below
                    "data": location_event,
                }
            )

            ack_event = build_envelope(
                event_type=SocketEventType.LOCATION_ACK.value,
                trip_id=resolved_trip_id,
                payload={"received_event_id": location_event["id"]},
            )
            await self.send(text_data=json.dumps(ack_event))

        elif action == "trip_tracking_started":
            trip_id = data.get("trip_id")
            user = self.scope.get("user")
            scope_user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
            resolved_trip_id, trip_state, context_error = await get_booking_stream_context(
                trip_id=trip_id,
                socket_driver_id=self.driver_id,
                scope_user_id=scope_user_id,
            )
            if context_error:
                await self.send(text_data=json.dumps({
                    "error": context_error,
                    "detail": "Could not authorize this trip stream",
                }))
                return
            if not can_stream_location(actor_role="driver", trip_state=trip_state):
                await self.send(text_data=json.dumps({
                    "error": "stream_not_allowed",
                    "detail": (
                        "Tracking can only start when trip state is "
                        f"{TripState.EN_ROUTE_TO_PICKUP.value}"
                    ),
                }))
                return
            try:
                tracking_started_event = build_envelope(
                    event_type=SocketEventType.TRIP_TRACKING_STARTED.value,
                    trip_id=resolved_trip_id,
                    payload=data.get("payload", {}),
                )
            except ValueError as exc:
                await self.send(text_data=json.dumps({
                    "error": "invalid_event",
                    "detail": str(exc),
                }))
                return
            await self.send(text_data=json.dumps(tracking_started_event))

        elif action == "trip_tracking_stopped":
            trip_id = data.get("trip_id")
            user = self.scope.get("user")
            scope_user_id = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
            resolved_trip_id, _, context_error = await get_booking_stream_context(
                trip_id=trip_id,
                socket_driver_id=self.driver_id,
                scope_user_id=scope_user_id,
            )
            if context_error:
                await self.send(text_data=json.dumps({
                    "error": context_error,
                    "detail": "Could not authorize this trip stream",
                }))
                return
            try:
                tracking_stopped_event = build_envelope(
                    event_type=SocketEventType.TRIP_TRACKING_STOPPED.value,
                    trip_id=resolved_trip_id,
                    payload=data.get("payload", {}),
                )
            except ValueError as exc:
                await self.send(text_data=json.dumps({
                    "error": "invalid_event",
                    "detail": str(exc),
                }))
                return
            await self.send(text_data=json.dumps(tracking_stopped_event))

        elif action == "status":
            # driver 'online' / 'offline' / 'busy' etc
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "driver_update",
                    "data": {
                        "action": "status",
                        "payload": data
                    }
                }
            )
            await self.send(text_data=json.dumps({"status": "ok", "action": "status_received"}))

        elif action == "heartbeat":
            # simple keep-alive; you might update last_seen timestamp
            await self.send(text_data=json.dumps({"status": "ok", "action": "heartbeat_ack"}))

        elif action == "exchange_token":
            # If you exchange tokens, validate/process here (careful with secrets over WS)
            # Example: echo back a confirmation (in real use, validate on server)
            await self.send(text_data=json.dumps({"status": "ok", "action": "token_received"}))

        else:
            # Unknown/unsupported action
            await self.send(text_data=json.dumps({
                "error": "unsupported_action",
                "detail": f"Unknown action: {action}"
            }))

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Handler invoked by channel_layer.group_send with "type": "driver_update"
    async def driver_update(self, event):
        """
        event is expected to contain a 'data' key with payload we forward to websocket clients.
        This method name must match the 'type' in group_send (dots replaced by underscores).
        """
        await self.send(text_data=json.dumps(event["data"]))


#User consumers
class UserConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        """
        User connects with a driver_id in the WS URL.
        Example:
        ws/users/track/<driver_id>/
        """
        self.driver_id = self.scope["url_route"]["kwargs"]["driver_id"]
        self.group_name = f"driver_{self.driver_id}_users"

        # Join user to this driver's tracking group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Optional: tell the user the socket is active
        await self.send(json.dumps({
            "status": "connected",
            "tracking_driver": self.driver_id
        }))

    async def receive(self, text_data):
        """
        Users normally do not send messages.
        But you can define actions here like:
        - ping
        - stop_tracking
        - request_last_location
        """
        try:
            data = json.loads(text_data)
        except:
            return

        action = data.get("action")

        if action == "ping":
            await self.send(json.dumps({"status": "pong"}))

        elif action == "request_last_location":
            # OPTIONAL: fetch Redis cache
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            last_loc_raw = r.get(f"driver:{self.driver_id}:location")

            if last_loc_raw:
                await self.send(last_loc_raw)
            else:
                await self.send(json.dumps({"error": "No location set"}))

    async def driver_location(self, event):
        """
        Called by DriverConsumer's group_send:
        {
          "type": "driver_location",
          "data": { ...coords... }
        }
        """

        await self.send(text_data=json.dumps(event["data"]))

    async def disconnect(self, close_code):
        # Remove user from tracking group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
