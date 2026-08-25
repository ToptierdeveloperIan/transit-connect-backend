from django.test import SimpleTestCase

from .event_reducer import reduce_payment_state
from .models import PaymentEventType, PaymentLifecycleState


class PaymentReducerTests(SimpleTestCase):
    def apply(self, events):
        state = PaymentLifecycleState.NONE
        for event_type in events:
            state, _, _ = reduce_payment_state(state, event_type)
        return state

    def test_provider_success_flow(self):
        state = self.apply([
            PaymentEventType.PAYMENT_CREATED,
            PaymentEventType.PAYMENT_REQUESTED,
            PaymentEventType.PROVIDER_ACCEPTED,
            PaymentEventType.PROVIDER_CONFIRMED_SUCCESS,
        ])
        self.assertEqual(state, PaymentLifecycleState.SUCCEEDED)

    def test_late_failure_does_not_override_success(self):
        state = self.apply([
            PaymentEventType.PAYMENT_CREATED,
            PaymentEventType.PAYMENT_REQUESTED,
            PaymentEventType.PROVIDER_CONFIRMED_SUCCESS,
        ])
        next_state, applied, _ = reduce_payment_state(
            state,
            PaymentEventType.PROVIDER_CONFIRMED_FAILURE,
        )
        self.assertFalse(applied)
        self.assertEqual(next_state, PaymentLifecycleState.SUCCEEDED)

    def test_reconciliation_can_correct_timeout(self):
        state = self.apply([
            PaymentEventType.PAYMENT_CREATED,
            PaymentEventType.PAYMENT_REQUESTED,
            PaymentEventType.PAYMENT_TIMEOUT_REACHED,
            PaymentEventType.RECONCILIATION_STARTED,
            PaymentEventType.RECONCILIATION_RESOLVED_SUCCESS,
        ])
        self.assertEqual(state, PaymentLifecycleState.SUCCEEDED)
