from django.db import transaction
from django.utils import timezone

from .event_reducer import reduce_payment_state
from .models import (
    PaymentEvent,
    PaymentLifecycleState,
    PaymentOutbox,
    PaymentOutboxStatus,
    PaymentProjection,
)


@transaction.atomic
def emit_payment_event(
    *,
    payment_id,
    event_type,
    source,
    correlation_id=None,
    provider_reference=None,
    payload=None,
    occurred_at=None,
):
    """
    Persist a payment event and an outbox row atomically.

    The request thread never publishes directly to Kafka. Publishing happens in
    payment_publish_outbox so a crash cannot lose an event after DB commit.
    """
    event = PaymentEvent.objects.create(
        payment_id=payment_id,
        event_type=event_type,
        occurred_at=occurred_at or timezone.now(),
        source=source,
        correlation_id=correlation_id,
        provider_reference=provider_reference,
        payload=payload or {},
    )
    PaymentOutbox.objects.create(event=event)
    return event


@transaction.atomic
def store_incoming_payment_event(event_payload):
    """
    Store an event received from Kafka, then apply it to the projection.

    get_or_create gives idempotency for repeated Kafka deliveries of the same
    eventId.
    """
    event, _ = PaymentEvent.objects.get_or_create(
        event_id=event_payload['eventId'],
        defaults={
            'payment_id': event_payload['paymentId'],
            'event_type': event_payload['eventType'],
            'occurred_at': event_payload.get('occurredAt') or timezone.now(),
            'source': event_payload.get('source', 'kafka'),
            'correlation_id': event_payload.get('correlationId'),
            'provider_reference': event_payload.get('providerReference'),
            'payload': event_payload.get('payload') or {},
        },
    )
    return apply_payment_event(event)


@transaction.atomic
def apply_payment_event(event):
    """
    Apply one immutable event to the current payment projection.

    The projection row is locked per payment_id, which keeps concurrent
    consumers from racing while Kafka preserves ordering for one key.
    """
    locked_event = PaymentEvent.objects.select_for_update().get(pk=event.pk)
    if locked_event.applied_at:
        return False, locked_event.ignored_reason or 'event-already-applied'

    projection, _ = PaymentProjection.objects.select_for_update().get_or_create(
        payment_id=locked_event.payment_id,
        defaults={'current_state': PaymentLifecycleState.NONE},
    )
    next_state, applied, reason = reduce_payment_state(
        projection.current_state,
        locked_event.event_type,
    )

    if applied:
        projection.current_state = next_state
        projection.last_event_id = locked_event.event_id
        projection.last_event_type = locked_event.event_type
        projection.provider_reference = (
            locked_event.provider_reference or projection.provider_reference
        )
        projection.version += 1
        projection.save(update_fields=[
            'current_state',
            'last_event_id',
            'last_event_type',
            'provider_reference',
            'version',
            'updated_at',
        ])

    locked_event.applied_at = timezone.now()
    locked_event.ignored_reason = '' if applied else reason
    locked_event.save(update_fields=['applied_at', 'ignored_reason'])
    return applied, reason


def mark_outbox_published(outbox_record):
    outbox_record.status = PaymentOutboxStatus.PUBLISHED
    outbox_record.published_at = timezone.now()
    outbox_record.last_error = ''
    outbox_record.save(update_fields=['status', 'published_at', 'last_error'])


def mark_outbox_failed(outbox_record, error):
    outbox_record.status = PaymentOutboxStatus.FAILED
    outbox_record.attempts += 1
    outbox_record.last_error = str(error)
    outbox_record.save(update_fields=['status', 'attempts', 'last_error'])