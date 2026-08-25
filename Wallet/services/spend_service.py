"""
Spend from wallet for a ride (or similar).

================================================================================
AMOUNT SOURCE OF TRUTH
================================================================================
Pay amount = FareQuote.discounted_fare, exposed by:

  paymentSystem.fare_bridge.payment_amount_for_quote(quote_id)

We store the amount on WalletIntent for audit/robustness, but re-read the
bridge at settle time so we never invent prices in the wallet layer.

================================================================================
CANONICAL DEDUCT RULE
================================================================================
Ledger DEBIT_SPEND posts only when we intentionally settle a spend intent
that is allowed to settle (e.g. user chose wallet pay + funds available).

There is no "optimistic debit" that later hopes the provider confirms —
wallet spend *is* internal, so success is the ledger post itself.

If an external rail is involved later (hybrid), still: debit only after the
event you define as canonical in POLICY.md.

================================================================================
REVERSAL
================================================================================
Refund / cancel after spend → CREDIT_REVERSAL via LedgerService.reverse_entry
on the DEBIT_SPEND row. No in-place mutation. No dual-balance hacks.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from paymentSystem.fare_bridge import payment_amount_for_quote
from Wallet.models import (
    IntentKind,
    IntentStatus,
    LedgerEntryType,
    ProviderChannel,
    WalletIntent,
)
from Wallet.services.exceptions import AmountMismatchError, IntentStateError, WalletError
from Wallet.services.ledger_service import LedgerService
from Wallet.services.wallet_service import WalletService


class SpendService:
    """Wallet pay for a fare quote (amount from FareQuoteService bridge)."""

    @classmethod
    @transaction.atomic
    def create_and_settle_spend(
        cls,
        user,
        *,
        quote_id: UUID | str,
        idempotency_key: str,
        booking_id: Optional[int] = None,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Read canonical fare amount, ensure funds, post DEBIT_SPEND in one txn.

        Idempotent on ``idempotency_key``.
        """
        key = (idempotency_key or "").strip()
        if not key:
            raise WalletError("idempotency_key is required", code="idempotency_required")

        existing = WalletIntent.objects.filter(idempotency_key=key).first()
        if existing:
            if existing.status == IntentStatus.SUCCEEDED:
                return cls._intent_payload(existing)
            raise IntentStateError(
                f"Intent exists in status {existing.status}",
                code="idempotency_conflict",
            )

        # --- Source of truth for amount (not client-supplied) ---
        try:
            amount = payment_amount_for_quote(quote_id)
        except Exception as exc:
            raise WalletError(
                f"Cannot resolve fare for quote: {exc}",
                code="quote_unavailable",
                status=400,
            ) from exc

        amount = Decimal(amount)
        if amount <= 0:
            raise AmountMismatchError("Quote payment amount must be positive")

        wallet = WalletService.get_or_create_for_user(user)
        locked = wallet.__class__.objects.select_for_update().get(pk=wallet.pk)
        spendable = locked.available_balance - locked.held_balance
        if spendable < amount:
            raise WalletError(
                "Insufficient wallet balance",
                code="insufficient_funds",
                status=402,
            )

        intent = WalletIntent.objects.create(
            wallet=locked,
            kind=IntentKind.SPEND,
            status=IntentStatus.CREATED,
            channel=ProviderChannel.WALLET,
            amount=amount,
            currency=locked.currency,
            idempotency_key=key,
            fare_quote_id=UUID(str(quote_id)),
            booking_id=booking_id,
            description=description or f"Wallet pay quote {quote_id}",
        )

        # Canonical internal success = ledger debit succeeds.
        entry = LedgerService.post_entry(
            locked,
            entry_type=LedgerEntryType.DEBIT_SPEND,
            amount=amount,
            intent=intent,
            channel=ProviderChannel.WALLET,
            description=intent.description,
            metadata={
                "quote_id": str(quote_id),
                "booking_id": booking_id,
                "amount_source": "fare_bridge.payment_amount_for_quote",
            },
        )

        intent.status = IntentStatus.SUCCEEDED
        intent.succeeded_at = timezone.now()
        intent.save(update_fields=["status", "succeeded_at", "updated_at"])

        payload = cls._intent_payload(intent)
        payload["ledger_entry_id"] = str(entry.id)
        return payload

    @classmethod
    @transaction.atomic
    def reverse_spend(
        cls,
        intent_id,
        *,
        reason: str = "spend_reversed",
    ) -> dict[str, Any]:
        """
        Reverse a successful wallet spend (compensating credit).

        Does not invent new amounts — uses original debit row amount.
        """
        intent = WalletIntent.objects.select_for_update().get(pk=intent_id)
        if intent.kind != IntentKind.SPEND:
            raise IntentStateError("Not a spend intent")
        if intent.status not in (IntentStatus.SUCCEEDED, IntentStatus.REVERSED):
            raise IntentStateError(f"Cannot reverse spend in status {intent.status}")

        debit = (
            intent.ledger_entries.filter(entry_type=LedgerEntryType.DEBIT_SPEND)
            .order_by("created_at")
            .first()
        )
        if debit is None:
            raise WalletError("No debit entry to reverse", code="missing_debit")

        if intent.status == IntentStatus.REVERSED:
            # Already reversed — return current state
            return cls._intent_payload(intent)

        rev = LedgerService.reverse_entry(debit, reason=reason, intent=intent)
        return {
            **cls._intent_payload(intent),
            "reversal_entry_id": str(rev.id),
        }

    @staticmethod
    def _intent_payload(intent: WalletIntent) -> dict[str, Any]:
        return {
            "intent_id": str(intent.id),
            "kind": intent.kind,
            "status": intent.status,
            "amount": str(intent.amount),
            "currency": intent.currency,
            "fare_quote_id": str(intent.fare_quote_id) if intent.fare_quote_id else None,
            "booking_id": intent.booking_id,
            "channel": intent.channel,
        }
