from .models import PaymentEventType, PaymentLifecycleState


TERMINAL_STATES = {
    PaymentLifecycleState.SUCCEEDED,
    PaymentLifecycleState.FAILED,
}


def _is_pending(state):
    return state in {
        PaymentLifecycleState.REQUESTED,
        PaymentLifecycleState.PROVIDER_PENDING,
        PaymentLifecycleState.TIMED_OUT,
    }


def _can_resolve(state):
    return state in {
        PaymentLifecycleState.REQUESTED,
        PaymentLifecycleState.PROVIDER_PENDING,
        PaymentLifecycleState.TIMED_OUT,
        PaymentLifecycleState.RECONCILING,
    }


def _can_fail(state):
    return state in {
        PaymentLifecycleState.REQUESTED,
        PaymentLifecycleState.PROVIDER_PENDING,
        PaymentLifecycleState.RECONCILING,
    }


def _can_reconcile(state):
    return state in {
        PaymentLifecycleState.TIMED_OUT,
        PaymentLifecycleState.RECONCILING,
        PaymentLifecycleState.PROVIDER_PENDING,
    }


def _keep(state, reason):
    return state, False, reason


def _move(next_state):
    return next_state, True, 'transition-applied'


def reduce_payment_state(current_state, event_type):
    """
    Deterministic payment state machine.

    Every consumer must use this reducer so replaying the same events converges
    to the same state even if machines receive duplicate Kafka messages.
    """
    state = current_state or PaymentLifecycleState.NONE

    # Provider success/failure is terminal for normal provider callbacks. A
    # reconciliation success is allowed to correct an earlier failure or timeout.
    if (
        state in TERMINAL_STATES
        and event_type != PaymentEventType.RECONCILIATION_RESOLVED_SUCCESS
    ):
        return _keep(state, 'terminal-state-already-reached')

    if event_type == PaymentEventType.PAYMENT_CREATED:
        return _move(PaymentLifecycleState.CREATED) if state == PaymentLifecycleState.NONE else _keep(state, 'payment-already-created')

    if event_type == PaymentEventType.PAYMENT_REQUESTED:
        return _move(PaymentLifecycleState.REQUESTED) if state == PaymentLifecycleState.CREATED else _keep(state, 'payment-not-created')

    if event_type == PaymentEventType.PROVIDER_ACCEPTED:
        return _move(PaymentLifecycleState.PROVIDER_PENDING) if state == PaymentLifecycleState.REQUESTED else _keep(state, 'payment-not-requested')

    if event_type == PaymentEventType.PROVIDER_CONFIRMED_SUCCESS:
        return _move(PaymentLifecycleState.SUCCEEDED) if _can_resolve(state) else _keep(state, 'payment-cannot-resolve-success')

    if event_type == PaymentEventType.PROVIDER_CONFIRMED_FAILURE:
        return _move(PaymentLifecycleState.FAILED) if _can_fail(state) else _keep(state, 'payment-cannot-resolve-failure')

    if event_type == PaymentEventType.PAYMENT_TIMEOUT_REACHED:
        return _move(PaymentLifecycleState.TIMED_OUT) if _is_pending(state) else _keep(state, 'payment-not-pending')

    if event_type == PaymentEventType.RECONCILIATION_STARTED:
        return _move(PaymentLifecycleState.RECONCILING) if _can_reconcile(state) else _keep(state, 'payment-not-reconcilable')

    if event_type == PaymentEventType.RECONCILIATION_RESOLVED_SUCCESS:
        return _move(PaymentLifecycleState.SUCCEEDED) if _can_reconcile(state) or state == PaymentLifecycleState.FAILED else _keep(state, 'payment-cannot-reconcile-success')

    if event_type == PaymentEventType.RECONCILIATION_RESOLVED_FAILURE:
        return _move(PaymentLifecycleState.FAILED) if _can_reconcile(state) else _keep(state, 'payment-cannot-reconcile-failure')

    return _keep(state, 'unknown-event-type')