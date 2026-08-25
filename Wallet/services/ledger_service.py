"""
Append-only ledger writer.

Rules:
  - Never UPDATE LedgerEntry amount/type after insert.
  - Reversal = new opposite entry + optional intent status REVERSED.
  - WalletAccount balances updated under select_for_update in same txn.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from Wallet.models import (
    IntentStatus,
    LedgerEntry,
    LedgerEntryType,
    WalletAccount,
    WalletIntent,
)
from Wallet.services.exceptions import IntentStateError, WalletError

# Map entry type → signed effect on available_balance
_CREDIT_TYPES = {
    LedgerEntryType.CREDIT_DEPOSIT,
    LedgerEntryType.CREDIT_REVERSAL,
    LedgerEntryType.CREDIT_ADJUSTMENT,
}
_DEBIT_TYPES = {
    LedgerEntryType.DEBIT_SPEND,
    LedgerEntryType.DEBIT_REVERSAL,
    LedgerEntryType.DEBIT_ADJUSTMENT,
}


class LedgerService:
    """Low-level ledger posts. Prefer DepositService / SpendService for product flows."""

    @staticmethod
    def get_or_create_wallet(user) -> WalletAccount:
        wallet, _ = WalletAccount.objects.get_or_create(user=user)
        return wallet

    @classmethod
    @transaction.atomic
    def post_entry(
        cls,
        wallet: WalletAccount,
        *,
        entry_type: str,
        amount: Decimal,
        intent: Optional[WalletIntent] = None,
        channel: str = "",
        provider_reference: str = "",
        description: str = "",
        metadata: Optional[dict[str, Any]] = None,
        related_entry: Optional[LedgerEntry] = None,
    ) -> LedgerEntry:
        """
        Insert one immutable ledger row and update cached balances.

        ``amount`` must be positive; direction is ``entry_type``.
        """
        amount = Decimal(amount)
        if amount <= 0:
            raise WalletError("Ledger amount must be positive", code="invalid_amount")

        locked = WalletAccount.objects.select_for_update().get(pk=wallet.pk)
        signed = amount if entry_type in _CREDIT_TYPES else -amount

        if entry_type in _DEBIT_TYPES:
            # Hold-aware spendable check
            spendable = locked.available_balance - locked.held_balance
            if spendable < amount and entry_type == LedgerEntryType.DEBIT_SPEND:
                raise WalletError(
                    "Insufficient available balance for debit",
                    code="insufficient_funds",
                    status=402,
                )

        new_available = locked.available_balance + signed
        if new_available < 0:
            raise WalletError(
                "Balance would go negative",
                code="insufficient_funds",
                status=402,
            )

        locked.available_balance = new_available
        locked.save(update_fields=["available_balance", "updated_at"])

        entry = LedgerEntry.objects.create(
            wallet=locked,
            entry_type=entry_type,
            amount=amount,
            currency=locked.currency,
            intent=intent,
            related_entry=related_entry,
            channel=channel or "",
            provider_reference=provider_reference or "",
            description=description or "",
            metadata=metadata or {},
            balance_after=new_available,
        )
        return entry

    @classmethod
    @transaction.atomic
    def reverse_entry(
        cls,
        original: LedgerEntry,
        *,
        reason: str,
        intent: Optional[WalletIntent] = None,
    ) -> LedgerEntry:
        """
        Compensating entry — does not delete or mutate ``original``.

        CREDIT_DEPOSIT → DEBIT_REVERSAL
        DEBIT_SPEND    → CREDIT_REVERSAL
        """
        if original.related_entry_id and original.entry_type in (
            LedgerEntryType.CREDIT_REVERSAL,
            LedgerEntryType.DEBIT_REVERSAL,
        ):
            raise WalletError("Cannot reverse a reversal entry", code="invalid_reversal")

        # Prevent double-reverse of same original
        if LedgerEntry.objects.filter(related_entry=original).exists():
            raise WalletError(
                "This ledger entry was already reversed",
                code="already_reversed",
                status=409,
            )

        if original.entry_type in _CREDIT_TYPES:
            reverse_type = LedgerEntryType.DEBIT_REVERSAL
        elif original.entry_type in _DEBIT_TYPES:
            reverse_type = LedgerEntryType.CREDIT_REVERSAL
        else:
            raise WalletError("Unknown entry type for reversal", code="invalid_entry_type")

        entry = cls.post_entry(
            original.wallet,
            entry_type=reverse_type,
            amount=original.amount,
            intent=intent or original.intent,
            channel=original.channel,
            provider_reference=original.provider_reference,
            description=f"Reversal: {reason}"[:255],
            metadata={"reversed_entry_id": str(original.id), "reason": reason},
            related_entry=original,
        )

        if intent or original.intent_id:
            target = intent or original.intent
            if target and target.status == IntentStatus.SUCCEEDED:
                target.status = IntentStatus.REVERSED
                target.failure_reason = reason[:255]
                target.save(update_fields=["status", "failure_reason", "updated_at"])

        return entry

    @staticmethod
    def rebuild_balance(wallet_id) -> Decimal:
        """
        Recompute available_balance from ledger (ops / reconciliation tool).
        Does not change holds.
        """
        total = Decimal("0")
        for e in LedgerEntry.objects.filter(wallet_id=wallet_id).order_by("created_at", "id"):
            total += e.signed_amount
        with transaction.atomic():
            w = WalletAccount.objects.select_for_update().get(pk=wallet_id)
            w.available_balance = total
            w.save(update_fields=["available_balance", "updated_at"])
        return total
