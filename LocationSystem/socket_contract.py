import uuid
from datetime import datetime, timezone
from enum import Enum


class TripState(str, Enum):
    EN_ROUTE_TO_PICKUP = "EN_ROUTE_TO_PICKUP"
    COLLECTING = "COLLECTING"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SocketEventType(str, Enum):
    LOCATION_UPDATE = "location.update"
    LOCATION_ACK = "location.ack"
    TRIP_TRACKING_STARTED = "trip.tracking_started"
    TRIP_TRACKING_STOPPED = "trip.tracking_stopped"


ALLOWED_LOCATION_STREAM_STATES = {TripState.EN_ROUTE_TO_PICKUP.value}
DRIVER_ROLE = "driver"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def can_stream_location(*, actor_role: str, trip_state: str) -> bool:
    return actor_role == DRIVER_ROLE and trip_state in ALLOWED_LOCATION_STREAM_STATES


def build_envelope(
    *,
    event_type: str,
    trip_id,
    payload: dict,
    event_id: str | None = None,
    ts: str | None = None,
) -> dict:
    if not event_type:
        raise ValueError("event_type is required")
    if trip_id in (None, ""):
        raise ValueError("trip_id is required")
    if payload is None:
        raise ValueError("payload is required")

    return {
        "id": event_id or str(uuid.uuid4()),
        "type": event_type,
        "ts": ts or _utc_now_iso(),
        "trip_id": str(trip_id),
        "payload": payload,
    }


def validate_envelope(event: dict) -> None:
    if not isinstance(event, dict):
        raise ValueError("event must be an object")

    required_fields = ("id", "type", "ts", "trip_id", "payload")
    missing = [field for field in required_fields if field not in event]
    if missing:
        raise ValueError(f"missing envelope fields: {', '.join(missing)}")

    if not isinstance(event["payload"], dict):
        raise ValueError("payload must be an object")
