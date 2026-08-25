from django.test import TestCase
from LocationSystem.socket_contract import (
    SocketEventType,
    TripState,
    build_envelope,
    can_stream_location,
    validate_envelope,
)


class SocketContractTests(TestCase):
    def test_driver_streaming_allowed_only_in_enroute_pickup(self):
        self.assertTrue(
            can_stream_location(
                actor_role="driver",
                trip_state=TripState.EN_ROUTE_TO_PICKUP.value,
            )
        )
        self.assertFalse(
            can_stream_location(
                actor_role="driver",
                trip_state=TripState.COLLECTING.value,
            )
        )
        self.assertFalse(
            can_stream_location(
                actor_role="rider",
                trip_state=TripState.EN_ROUTE_TO_PICKUP.value,
            )
        )

    def test_build_and_validate_envelope(self):
        event = build_envelope(
            event_type=SocketEventType.LOCATION_UPDATE.value,
            trip_id=123,
            payload={"lat": 1.0, "lng": 36.0},
        )
        validate_envelope(event)
        self.assertEqual(event["type"], "location.update")
        self.assertEqual(event["trip_id"], "123")

    def test_validate_envelope_missing_fields_raises(self):
        with self.assertRaises(ValueError):
            validate_envelope({"type": "location.update"})
