"""
Read models + account lifecycle for Wallet.
"""

from __future__ import annotations

from typing import Any

from Wallet.models import LedgerEntry, WalletAccount, WalletIntent
from Wallet.services.ledger_service import LedgerService


class WalletService:
    """User-facing wallet reads and ensure-account."""

    @staticmethod
    def get_or_create_for_user(user) -> WalletAccount:
        return LedgerService.get_or_create_wallet(user)

    @classmethod
    def get_balance_snapshot(cls, user) -> dict[str, Any]:
        wallet = cls.get_or_create_for_user(user)
        return {
            "wallet_id": str(wallet.id),
            "currency": wallet.currency,
            "available_balance": str(wallet.available_balance),
            "held_balance": str(wallet.held_balance),
            "spendable": str(wallet.spendable),
            "is_active": wallet.is_active,
            "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else None,
        }

    @classmethod
    def list_ledger(cls, user, *, limit: int = 50) -> list[dict[str, Any]]:
        wallet = cls.get_or_create_for_user(user)
        qs = LedgerEntry.objects.filter(wallet=wallet).order_by("-created_at")[:limit]
        return [
            {
                "id": str(e.id),
                "entry_type": e.entry_type,
                "amount": str(e.amount),
                "signed_amount": str(e.signed_amount),
                "currency": e.currency,
                "channel": e.channel,
                "provider_reference": e.provider_reference,
                "description": e.description,
                "balance_after": str(e.balance_after),
                "intent_id": str(e.intent_id) if e.intent_id else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in qs
        ]

    @classmethod
    def list_intents(cls, user, *, limit: int = 30) -> list[dict[str, Any]]:
        wallet = cls.get_or_create_for_user(user)
        qs = WalletIntent.objects.filter(wallet=wallet).order_by("-created_at")[:limit]
        return [
            {
                "id": str(i.id),
                "kind": i.kind,
                "status": i.status,
                "channel": i.channel,
                "amount": str(i.amount),
                "currency": i.currency,
                "provider_reference": i.provider_reference,
                "fare_quote_id": str(i.fare_quote_id) if i.fare_quote_id else None,
                "description": i.description,
                "created_at": i.created_at.isoformat(),
                "succeeded_at": i.succeeded_at.isoformat() if i.succeeded_at else None,
            }
            for i in qs
        ]
