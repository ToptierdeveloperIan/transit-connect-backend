import uuid

from django.db import models
from Loginandauthentication.models import CustomUser


class STKPushTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='stk_transactions')
    booking = models.ForeignKey('ride_matching.Booking', on_delete=models.SET_NULL, null=True, blank=True, related_name='stk_transactions')
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    merchant_request_id = models.CharField(max_length=100, unique=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    result_code = models.CharField(max_length=10, null=True, blank=True)
    result_desc = models.TextField(null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"STK {self.checkout_request_id} | {self.phone_number} | {self.status}"


class B2CTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]

    COMMAND_CHOICES = [
        ('BusinessPayment', 'Business Payment'),
        ('SalaryPayment', 'Salary Payment'),
        ('PromotionPayment', 'Promotion Payment'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='b2c_transactions')
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    command_id = models.CharField(max_length=30, choices=COMMAND_CHOICES, default='BusinessPayment')
    originator_conversation_id = models.CharField(max_length=100, unique=True)
    conversation_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    result_code = models.CharField(max_length=10, null=True, blank=True)
    result_desc = models.TextField(null=True, blank=True)
    transaction_id = models.CharField(max_length=50, null=True, blank=True)
    remarks = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"B2C {self.originator_conversation_id} | {self.phone_number} | {self.status}"


class PaymentEventType(models.TextChoices):
    PAYMENT_CREATED = 'PAYMENT_CREATED', 'Payment created'
    PAYMENT_REQUESTED = 'PAYMENT_REQUESTED', 'Payment requested'
    PROVIDER_ACCEPTED = 'PROVIDER_ACCEPTED', 'Provider accepted'
    PROVIDER_CONFIRMED_SUCCESS = 'PROVIDER_CONFIRMED_SUCCESS', 'Provider confirmed success'
    PROVIDER_CONFIRMED_FAILURE = 'PROVIDER_CONFIRMED_FAILURE', 'Provider confirmed failure'
    PAYMENT_TIMEOUT_REACHED = 'PAYMENT_TIMEOUT_REACHED', 'Payment timeout reached'
    RECONCILIATION_STARTED = 'RECONCILIATION_STARTED', 'Reconciliation started'
    RECONCILIATION_RESOLVED_SUCCESS = 'RECONCILIATION_RESOLVED_SUCCESS', 'Reconciliation resolved success'
    RECONCILIATION_RESOLVED_FAILURE = 'RECONCILIATION_RESOLVED_FAILURE', 'Reconciliation resolved failure'


class PaymentLifecycleState(models.TextChoices):
    NONE = 'NONE', 'No state'
    CREATED = 'CREATED', 'Created'
    REQUESTED = 'REQUESTED', 'Requested'
    PROVIDER_PENDING = 'PROVIDER_PENDING', 'Provider pending'
    SUCCEEDED = 'SUCCEEDED', 'Succeeded'
    FAILED = 'FAILED', 'Failed'
    TIMED_OUT = 'TIMED_OUT', 'Timed out'
    RECONCILING = 'RECONCILING', 'Reconciling'


class PaymentOutboxStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PUBLISHED = 'PUBLISHED', 'Published'
    FAILED = 'FAILED', 'Failed'


class PaymentEvent(models.Model):
    """
    Immutable payment fact stored before/after Kafka transport.

    payment_id is the Kafka key and must identify one payment aggregate, for
    example an STK CheckoutRequestID or a B2C OriginatorConversationID.
    """
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payment_id = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=48, choices=PaymentEventType.choices)
    occurred_at = models.DateTimeField()
    source = models.CharField(max_length=80)
    correlation_id = models.CharField(max_length=120, null=True, blank=True)
    provider_reference = models.CharField(max_length=120, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    ignored_reason = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['occurred_at', 'id']
        indexes = [
            models.Index(fields=['payment_id', 'occurred_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f"{self.payment_id} | {self.event_type}"


class PaymentProjection(models.Model):
    """
    Current materialized payment state derived from PaymentEvent rows.

    Kafka remains the event transport; this table gives the API a fast and
    deterministic read model that can be rebuilt from events.
    """
    payment_id = models.CharField(max_length=120, primary_key=True)
    current_state = models.CharField(
        max_length=32,
        choices=PaymentLifecycleState.choices,
        default=PaymentLifecycleState.NONE,
    )
    last_event_id = models.UUIDField(null=True, blank=True)
    last_event_type = models.CharField(max_length=48, blank=True, default='')
    provider_reference = models.CharField(max_length=120, null=True, blank=True)
    version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.payment_id} | {self.current_state} | v{self.version}"


class PaymentOutbox(models.Model):
    """
    Producer-side reliability boundary.

    Create this row in the same DB transaction as the payment change, then let
    the management command publish it to Kafka and mark it as published.
    """
    outbox_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(PaymentEvent, on_delete=models.CASCADE, related_name='outbox_records')
    status = models.CharField(
        max_length=16,
        choices=PaymentOutboxStatus.choices,
        default=PaymentOutboxStatus.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f"{self.event.event_type} | {self.status}"
