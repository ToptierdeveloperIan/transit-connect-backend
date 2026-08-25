"""
Payment-side bridge to FareQuoteService (amount source of truth).

Does not re-price routes. Reads OPEN quotes only.

Usage in STK initiate (when wiring)::

    from paymentSystem.fare_bridge import payment_amount_for_quote, payment_payload_for_quote

    amount = payment_amount_for_quote(quote_id)
    # ... initiate STK with amount ...
    # on success:
    # mark_quote_paid(quote_id, booking=booking)

See ride_matching/FARE_QUOTE.md.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Union
from uuid import UUID

from ride_matching.models import Booking
from ride_matching.services.fare_quote_service import FareQuoteService


def payment_amount_for_quote(quote_id: Union[str, UUID]) -> Decimal:
    """
    Amount to charge = FareQuote.discounted_fare (OPEN, non-expired).
    Not a third field — discounted_fare is the pay amount.
    """
    return FareQuoteService().get_payment_amount(quote_id)


def payment_payload_for_quote(quote_id: Union[str, UUID]) -> dict[str, Any]:
    """Payload: amount aliases discounted_fare; also base_fare for display."""
    return FareQuoteService().get_payment_payload(quote_id)


def mark_quote_paid(
    quote_id: Union[str, UUID],
    booking: Optional[Booking] = None,
):
    """After provider confirms success — consume quote + clear Redis."""
    return FareQuoteService().mark_quote_consumed(quote_id, booking=booking)


def abandon_unpaid_quote(quote_id: Union[str, UUID], reason: str = "payment_abandoned"):
    """User cancelled / failed before success — clear quote state."""
    return FareQuoteService().abandon_quote(quote_id, reason=reason)
