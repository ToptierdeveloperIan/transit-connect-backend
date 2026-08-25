"""
Wallet deposits via M-Pesa or Airtel Money.

================================================================================
CANONICAL SUCCESS RULE
================================================================================
Creating a deposit intent + asking the provider for money does **not** credit
the ledger. Credit happens only in ``apply_provider_success`` when the provider
(or reconciliation) has **explicitly confirmed** payment.

Failure / timeout / cancel → intent terminal FAILED/EXPIRED, **zero** ledger rows.

Reversal of a completed deposit → compensating DEBIT_REVERSAL (new row), never
delete CREDIT_DEPOSIT.

Integration note:
  Wire STK/Airtel callbacks to ``apply_provider_success`` / ``apply_provider_failure``.
  Existing paymentSystem STK rows can set provider_reference = CheckoutRequestID.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from Wallet.models import (
    IntentKind,
    IntentStatus,
    LedgerEntryType,
    ProviderChannel,
    WalletIntent,
)
from Wallet.services.exceptions import IntentStateError, WalletError
from Wallet.services.ledger_service import LedgerService
from Wallet.services.wallet_service import WalletService


class DepositService:
    """Deposit intents + canonical credit on provider success."""

    ALLOWED_CHANNELS = {ProviderChannel.MPESA, ProviderChannel.AIRTEL}

    @classmethod
    @transaction.atomic
    def create_deposit_intent(
        cls,
        user,
        *,
        amount: Decimal,
        channel: str,
        idempotency_key: str,
        description: str = "",
    ) -> WalletIntent:
        """
        Record intent and mark PENDING_PROVIDER.

        Does **not** call Daraja/Airtel here — caller or a worker initiates the
        provider push and then sets provider_reference via ``attach_provider_reference``.
        """
        amount = Decimal(amount)
        if amount <= 0:
            raise WalletError("Deposit amount must be positive", code="invalid_amount")

        channel = (channel or "").upper()
        if channel not in cls.ALLOWED_CHANNELS:
            raise WalletError(
                f"Deposit channel must be MPESA or AIRTEL, got {channel}",
                code="invalid_channel",
            )

        key = (idempotency_key or "").strip()
        if not key:
            raise WalletError("idempotency_key is required", code="idempotency_required")

        existing = WalletIntent.objects.filter(idempotency_key=key).first()
        if existing:
            return existing

        wallet = WalletService.get_or_create_for_user(user)
        intent = WalletIntent.objects.create(
            wallet=wallet,
            kind=IntentKind.DEPOSIT,
            status=IntentStatus.PENDING_PROVIDER,
            channel=channel,
            amount=amount,
            currency=wallet.currency,
            idempotency_key=key,
            description=description or f"Deposit via {channel}",
        )
        return intent

    @classmethod
    def attach_provider_reference(
        cls,
        intent_id,
        *,
        provider_reference: str,
        provider_payload: Optional[dict] = None,
    ) -> WalletIntent:
        """Bind STK CheckoutRequestID / Airtel ref after provider accepts the request."""
        with transaction.atomic():
            intent = WalletIntent.objects.select_for_update().get(pk=intent_id)
            if intent.kind != IntentKind.DEPOSIT:
                raise IntentStateError("Not a deposit intent")
            if intent.status not in (
                IntentStatus.PENDING_PROVIDER,
                IntentStatus.PROVIDER_ACCEPTED,
                IntentStatus.CREATED,
            ):
                raise IntentStateError(
                    f"Cannot attach provider ref in status {intent.status}"
                )
            intent.provider_reference = provider_reference
            if provider_payload:
                intent.provider_payload = {
                    **(intent.provider_payload or {}),
                    **provider_payload,
                }
            intent.status = IntentStatus.PROVIDER_ACCEPTED
            intent.save(
                update_fields=[
                    "provider_reference",
                    "provider_payload",
                    "status",
                    "updated_at",
                ]
            )
            return intent

    @classmethod
    @transaction.atomic
    def apply_provider_success(
        cls,
        *,
        provider_reference: str,
        channel: str,
        amount: Optional[Decimal] = None,
        raw_payload: Optional[dict[str, Any]] = None,
    ) -> WalletIntent:
        """
        **Canonical success path.** Credits ledger once.

        Safe to call multiple times with the same provider_reference — second
        call is a no-op success (intent already SUCCEEDED).
        """
        channel = (channel or "").upper()
        intent = (
            WalletIntent.objects.select_for_update()
            .filter(
                kind=IntentKind.DEPOSIT,
                channel=channel,
                provider_reference=provider_reference,
            )
            .first()
        )
        if intent is None:
            raise WalletError(
                "No deposit intent for provider reference",
                code="intent_not_found",
                status=404,
            )

        if intent.status == IntentStatus.SUCCEEDED:
            return intent  # idempotent

        if intent.status == IntentStatus.REVERSED:
            raise IntentStateError("Deposit was reversed; cannot re-succeed")

        if intent.status not in (
            IntentStatus.PENDING_PROVIDER,
            IntentStatus.PROVIDER_ACCEPTED,
        ):
            raise IntentStateError(
                f"Deposit cannot succeed from status {intent.status}"
            )

        # Optional amount check (provider callback amount vs intent).
        if amount is not None and Decimal(amount) != intent.amount:
            raise WalletError(
                f"Provider amount {amount} != intent {intent.amount}",
                code="amount_mismatch",
            )

        # --- LEDGER CREDIT (only here) ---
        LedgerService.post_entry(
            intent.wallet,
            entry_type=LedgerEntryType.CREDIT_DEPOSIT,
            amount=intent.amount,
            intent=intent,
            channel=intent.channel,
            provider_reference=provider_reference,
            description=intent.description or "Wallet deposit",
            metadata={"raw": raw_payload or {}, "event": "PROVIDER_CONFIRMED_SUCCESS"},
        )

        intent.status = IntentStatus.SUCCEEDED
        intent.succeeded_at = timezone.now()
        if raw_payload:
            intent.provider_payload = {**(intent.provider_payload or {}), "success": raw_payload}
        intent.save(
            update_fields=["status", "succeeded_at", "provider_payload", "updated_at"]
        )
        return intent

    @classmethod
    @transaction.atomic
    def apply_provider_failure(
        cls,
        *,
        provider_reference: str,
        channel: str,
        reason: str = "provider_failed",
    ) -> WalletIntent:
        """Mark deposit failed — no ledger movement."""
        channel = (channel or "").upper()
        intent = (
            WalletIntent.objects.select_for_update()
            .filter(
                kind=IntentKind.DEPOSIT,
                channel=channel,
                provider_reference=provider_reference,
            )
            .first()
        )
        if intent is None:
            raise WalletError("No deposit intent for provider reference", code="intent_not_found", status=404)

        if intent.status == IntentStatus.SUCCEEDED:
            # Late failure after success is a **reversal** problem, not failure.
            raise IntentStateError(
                "Deposit already succeeded; use reverse path, not failure"
            )

        intent.status = IntentStatus.FAILED
        intent.failure_reason = (reason or "")[:255]
        intent.save(update_fields=["status", "failure_reason", "updated_at"])
        return intent
