"""
Wallet domain models — append-only ledger + intents.

================================================================================
DESIGN (scale-oriented, reversal-safe)
================================================================================
1. **LedgerEntry is immutable history.** Never update amount/type after insert.
   Reversals are *new* opposite entries linked via ``related_entry``.

2. **WalletAccount.available_balance** is a cached projection updated in the
   same DB transaction as ledger inserts (row lock). Rebuildable as SUM(entries).

3. **WalletIntent** tracks deposit/spend lifecycle with providers. Money does
   not move in the ledger until a **canonical success** event is applied
   (provider callback SUCCESS / recon SUCCESS). Failures leave zero ledger rows.

4. **Pay amount for rides** is NOT invented here:
   ``paymentSystem.fare_bridge.payment_amount_for_quote(quote_id)``
   → FareQuote.discounted_fare (see FARE_QUOTE.md).

5. **Idempotency:** unique constraints on (provider_channel, provider_reference)
   and intent.idempotency_key prevent double credit/debit under retries.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class ProviderChannel(models.TextChoices):
    """Rails that can fund or settle money movement."""

    MPESA = "MPESA", "M-Pesa"
    AIRTEL = "AIRTEL", "Airtel Money"
    INTERNAL = "INTERNAL", "Internal (ledger-only / adjustment)"
    WALLET = "WALLET", "Wallet balance (spend from available)"


class IntentKind(models.TextChoices):
    """What the user/system is trying to do."""

    DEPOSIT = "DEPOSIT", "Deposit into wallet"
    SPEND = "SPEND", "Spend from wallet (e.g. pay fare)"
    REFUND_TO_WALLET = "REFUND_TO_WALLET", "Credit wallet after refund path"
    ADJUSTMENT = "ADJUSTMENT", "Ops adjustment (audited)"


class IntentStatus(models.TextChoices):
    """
    Intent lifecycle. Ledger posts only from terminal SUCCESS paths.

    PENDING_PROVIDER → user challenged / STK sent
    PROVIDER_ACCEPTED → provider accepted request (not funded yet)
    SUCCEEDED → canonical success; ledger row(s) exist
    FAILED / EXPIRED / CANCELLED → no ledger movement
    REVERSED → original SUCCESS was later reversed via compensating ledger entry
    """

    CREATED = "CREATED", "Created"
    PENDING_PROVIDER = "PENDING_PROVIDER", "Pending provider"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED", "Provider accepted"
    SUCCEEDED = "SUCCEEDED", "Succeeded"
    FAILED = "FAILED", "Failed"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"
    REVERSED = "REVERSED", "Reversed"


class LedgerEntryType(models.TextChoices):
    """
    Signed money movements. Positive amounts only; direction is in type.

    CREDIT_* increases available_balance
    DEBIT_* decreases available_balance
    """

    CREDIT_DEPOSIT = "CREDIT_DEPOSIT", "Deposit credit"
    DEBIT_SPEND = "DEBIT_SPEND", "Spend debit"
    CREDIT_REVERSAL = "CREDIT_REVERSAL", "Reversal credit (undo debit)"
    DEBIT_REVERSAL = "DEBIT_REVERSAL", "Reversal debit (undo credit)"
    CREDIT_ADJUSTMENT = "CREDIT_ADJUSTMENT", "Adjustment credit"
    DEBIT_ADJUSTMENT = "DEBIT_ADJUSTMENT", "Adjustment debit"


class WalletAccount(models.Model):
    """
    One wallet per user (1:1). Balance cache is not source of truth —
    ledger is. Cache is updated transactionally for fast reads.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_account",
    )
    currency = models.CharField(max_length=3, default="KES")
    # Cached available funds (KES). Rebuild: sum of signed ledger effects.
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Funds reserved for in-flight SPEND intents (optional hold pattern).
    held_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"Wallet {self.user_id} bal={self.available_balance} {self.currency}"

    @property
    def spendable(self):
        """Amount that can be spent without touching holds."""
        return self.available_balance - self.held_balance


class WalletIntent(models.Model):
    """
    Deposit / spend request tracked until a canonical outcome.

    For DEPOSIT: amount is user-chosen (top-up).
    For SPEND: amount MUST come from FareQuote via fare_bridge (stored for
    audit; re-validated at settle time against OPEN quote when possible).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        WalletAccount,
        on_delete=models.CASCADE,
        related_name="intents",
    )
    kind = models.CharField(max_length=32, choices=IntentKind.choices, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=IntentStatus.choices,
        default=IntentStatus.CREATED,
        db_index=True,
    )
    channel = models.CharField(
        max_length=16,
        choices=ProviderChannel.choices,
        db_index=True,
    )
    # Absolute amount in wallet currency (positive).
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")

    # Client / server idempotency for create + retries.
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)

    # Provider correlation (STK CheckoutRequestID, Airtel txn id, …).
    provider_reference = models.CharField(
        max_length=120, null=True, blank=True, db_index=True
    )
    provider_payload = models.JSONField(default=dict, blank=True)

    # Spend linkage: fare truth + optional booking after pay.
    fare_quote_id = models.UUIDField(null=True, blank=True, db_index=True)
    booking_id = models.IntegerField(null=True, blank=True, db_index=True)

    # Human / support.
    description = models.CharField(max_length=255, blank=True, default="")
    failure_reason = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "status", "kind"]),
            models.Index(fields=["channel", "provider_reference"]),
        ]
        constraints = [
            # One provider ref per channel when set (prevents double credit).
            models.UniqueConstraint(
                fields=["channel", "provider_reference"],
                condition=Q(provider_reference__isnull=False)
                & ~Q(provider_reference=""),
                name="uniq_wallet_intent_channel_provider_ref",
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.amount} {self.status} [{self.channel}]"


class LedgerEntry(models.Model):
    """
    Immutable money fact. Append-only.

    Reversals: insert opposite entry with related_entry → original.
    Never mutate this row after create (admin should be read-only).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        WalletAccount,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(
        max_length=32, choices=LedgerEntryType.choices, db_index=True
    )
    # Always positive; sign is implied by entry_type.
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")

    # Optional link to the intent that authorized this movement.
    intent = models.ForeignKey(
        WalletIntent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
    )
    # Compensating entry graph (reversal → original).
    related_entry = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="compensations",
    )

    # Denormalized for audit without joins.
    channel = models.CharField(
        max_length=16, choices=ProviderChannel.choices, blank=True, default=""
    )
    provider_reference = models.CharField(max_length=120, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    # Running balance after this entry (audit aid; still rebuildable).
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["wallet", "created_at"]),
            models.Index(fields=["intent"]),
            models.Index(fields=["provider_reference"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount__gt=0),
                name="ledger_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount} wallet={self.wallet_id}"

    @property
    def signed_amount(self):
        """+credit / -debit for balance math."""
        if self.entry_type.startswith("CREDIT"):
            return self.amount
        return -self.amount
