"""
FareQuoteService — operator on ``fare`` inside get_route_coordinates.

================================================================================
ROLE
================================================================================
Two prices only:
  base_fare        — list price (Route.price); never null in DB
  discounted_fare  — what payment charges (= base if no valid promo)

There is NO separate amount_due field. Payment reads discounted_fare.

- Called from get_route_coordinates on the fare variable (does not replace coords).
- Validates promo (REDEEMED, owned, attempts > 0, time) or leaves base only.
- Persists OPEN quotes to Redis + DB; abandons/expires if user does not pay.

Payment: get_payment_amount(quote_id) → discounted_fare

Docs: ride_matching/FARE_QUOTE.md
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from typing import Any, Optional, Union

import redis
from django.db import transaction
from django.utils import timezone

from ride_matching.models import Booking, FareQuote

logger = logging.getLogger(__name__)

# Quote open window (user must complete payment or quote is expired/cleared)
QUOTE_TTL = timedelta(minutes=30)
REDIS_KEY_PREFIX = "fare_quote:"
REDIS_USER_LATEST_PREFIX = "fare_quote:user:"

# Provisional discount meaning: value is a PERCENT off base fare (0–100).
# Align with Checkout.calculate_fare until product freezes % vs fixed KES.
DISCOUNT_VALUE_IS_PERCENT = True


class FareQuoteError(ValueError):
    """Invalid quote / payment lookup."""


class FareQuoteService:
    """
    Operator on fare: base_fare → discounted_fare (pay amount).

    Used inside get_route_coordinates — does not replace coordinate lookup.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis = redis_client

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        return self._redis

    # ------------------------------------------------------------------
    # Public: used by get_route_coordinates
    # ------------------------------------------------------------------

    def apply_to_base_fare(
        self,
        base_fare: Union[int, float, Decimal],
        *,
        route_name: str,
        user=None,
        promo_code: Optional[str] = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """
        Main operator: given base fare, return pricing block for coordinates.

        Strict validation:
          - base_fare must be finite and >= 0
          - promo ignored unless user present, code valid, REDEEMED to that user,
            attempts > 0, time-valid
          - On any promo failure → base fare only (no crash)

        When persist=True and user is set, writes OPEN quote to Redis + DB.
        """
        base = self._coerce_money(base_fare, field="base_fare")
        if base < 0:
            raise FareQuoteError("base_fare must be >= 0")

        normalized_promo = (promo_code or "").strip().upper() or None
        promo_applied = False
        reject_reason: Optional[str] = None
        discounted = base

        if normalized_promo:
            ok, reason, discounted_candidate = self._try_apply_promo(
                base=base,
                user=user,
                promo_code=normalized_promo,
            )
            if ok:
                promo_applied = True
                discounted = discounted_candidate
            else:
                reject_reason = reason
                discounted = base
                normalized_promo = None  # do not attach failed promo to quote
        elif promo_code is not None and str(promo_code).strip() and user is None:
            reject_reason = "promo_requires_authenticated_user"
            discounted = base

        # Payment amount == discounted_fare (no third field)
        result: dict[str, Any] = {
            "fare": float(base),  # same as base_fare (coords legacy key)
            "base_fare": float(base),
            "discounted_fare": float(discounted),
            "promo_applied": promo_applied,
            "promo_code": normalized_promo if promo_applied else None,
            "promo_reject_reason": reject_reason,
            "quote_id": None,
            "quote_expires_at": None,
            "quote_status": None,
        }

        if persist and user is not None:
            quote = self._persist_open_quote(
                user=user,
                route_name=route_name,
                base_fare=base,
                discounted_fare=discounted,
                promo_code=normalized_promo if promo_applied else None,
                promo_applied=promo_applied,
                promo_reject_reason=reject_reason,
            )
            result["quote_id"] = str(quote.quote_id)
            result["quote_expires_at"] = quote.expires_at.isoformat()
            result["quote_status"] = quote.status
        elif persist and user is None:
            result["promo_reject_reason"] = result["promo_reject_reason"] or (
                "quote_not_persisted_anonymous"
            )

        return result

    # ------------------------------------------------------------------
    # Payment module surface — amount is discounted_fare
    # ------------------------------------------------------------------

    def get_payment_amount(self, quote_id: Union[str, uuid.UUID]) -> Decimal:
        """
        STK / payment amount = discounted_fare on an OPEN, non-expired quote.
        """
        quote = self._get_open_quote_or_raise(quote_id)
        return quote.discounted_fare

    def get_payment_payload(self, quote_id: Union[str, uuid.UUID]) -> dict[str, Any]:
        """Payload for payment initiation. ``amount`` aliases discounted_fare."""
        quote = self._get_open_quote_or_raise(quote_id)
        return {
            "quote_id": str(quote.quote_id),
            "amount": str(quote.discounted_fare),
            "base_fare": str(quote.base_fare),
            "discounted_fare": str(quote.discounted_fare),
            "promo_code": quote.promo_code,
            "promo_applied": quote.promo_applied,
            "route_name": quote.route_name,
            "user_id": quote.user_id,
            "currency": "KES",
            "expires_at": quote.expires_at.isoformat(),
            "status": quote.status,
        }

    def mark_quote_consumed(
        self,
        quote_id: Union[str, uuid.UUID],
        *,
        booking: Optional[Booking] = None,
    ) -> FareQuote:
        """Call after successful payment. Clears Redis open key."""
        with transaction.atomic():
            quote = FareQuote.objects.select_for_update().filter(
                quote_id=self._as_uuid(quote_id)
            ).first()
            if quote is None:
                raise FareQuoteError(f"Quote {quote_id} not found")
            if quote.status != FareQuote.Status.OPEN:
                raise FareQuoteError(
                    f"Quote {quote_id} is {quote.status}, cannot consume"
                )
            quote.status = FareQuote.Status.CONSUMED
            if booking is not None:
                quote.booking = booking
                self._copy_pricing_to_booking(booking, quote)
            quote.save()
        self._redis_delete_quote(quote)
        return quote

    def abandon_quote(self, quote_id: Union[str, uuid.UUID], *, reason: str = "") -> FareQuote:
        """
        User did not complete transaction — clear DB state + Redis.
        """
        with transaction.atomic():
            quote = FareQuote.objects.select_for_update().filter(
                quote_id=self._as_uuid(quote_id)
            ).first()
            if quote is None:
                raise FareQuoteError(f"Quote {quote_id} not found")
            if quote.status == FareQuote.Status.CONSUMED:
                raise FareQuoteError("Cannot abandon a consumed quote")
            quote.status = FareQuote.Status.ABANDONED
            if reason:
                quote.promo_reject_reason = (quote.promo_reject_reason or "")[:200]
            quote.save(update_fields=["status", "updated_at"])
        self._redis_delete_quote(quote)
        logger.info("FareQuote abandoned quote_id=%s reason=%s", quote_id, reason)
        return quote

    def monitor_and_expire_open_quotes(self) -> int:
        """
        State monitor: OPEN quotes past expires_at → EXPIRED + Redis clear.

        Run from cron / management command. Returns number expired.
        """
        now = timezone.now()
        expired_ids = list(
            FareQuote.objects.filter(
                status=FareQuote.Status.OPEN,
                expires_at__lte=now,
            ).values_list("id", "quote_id", "user_id")
        )
        if not expired_ids:
            return 0

        count = FareQuote.objects.filter(
            id__in=[row[0] for row in expired_ids],
            status=FareQuote.Status.OPEN,
        ).update(status=FareQuote.Status.EXPIRED)

        for _id, qid, user_id in expired_ids:
            self._redis_delete_keys(str(qid), user_id)

        logger.info("FareQuote monitor expired count=%s", count)
        return count

    def attach_quote_to_booking(
        self,
        quote_id: Union[str, uuid.UUID],
        booking: Booking,
    ) -> Booking:
        """Copy quote pricing onto Booking (nullable fare fields)."""
        quote = FareQuote.objects.filter(quote_id=self._as_uuid(quote_id)).first()
        if quote is None:
            raise FareQuoteError(f"Quote {quote_id} not found")
        self._copy_pricing_to_booking(booking, quote)
        quote.booking = booking
        quote.save(update_fields=["booking", "updated_at"])
        return booking

    # ------------------------------------------------------------------
    # Promo validation (strict)
    # ------------------------------------------------------------------

    def _try_apply_promo(
        self,
        *,
        base: Decimal,
        user,
        promo_code: str,
    ) -> tuple[bool, Optional[str], Decimal]:
        """
        Returns (ok, reject_reason, discounted_fare).

        Failures never raise — caller falls back to base fare.
        """
        if user is None:
            return False, "promo_requires_authenticated_user", base

        if not promo_code or len(promo_code) != 8:
            return False, "promo_code_invalid_format", base

        try:
            from RedeemAndRefferalSys.models import DiscountCode
            from RedeemAndRefferalSys.policy import is_time_valid
        except ImportError:
            return False, "promo_module_unavailable", base

        discount = DiscountCode.objects.filter(code=promo_code).first()
        if discount is None:
            return False, "promo_not_found", base

        if discount.status != DiscountCode.Status.REDEEMED:
            return False, f"promo_status_not_redeemed:{discount.status}", base

        if discount.redeemed_by_user_id != getattr(user, "id", None):
            return False, "promo_not_owned_by_user", base

        attempts = int(discount.allowed_attempts or 0)
        if attempts <= 0:
            return False, "promo_attempts_exhausted", base

        if not is_time_valid(discount):
            return False, "promo_time_expired", base

        try:
            discounted = self._compute_discounted(base, discount)
        except FareQuoteError as exc:
            return False, str(exc), base

        if discounted < 0 or discounted > base:
            return False, "promo_discount_out_of_range", base

        return True, None, discounted

    def _compute_discounted(self, base: Decimal, discount) -> Decimal:
        raw = discount.value if discount.value is not None else discount.Value_of_code
        value = self._coerce_money(raw, field="promo_value")

        if DISCOUNT_VALUE_IS_PERCENT:
            if value > 100:
                raise FareQuoteError("promo_percent_exceeds_100")
            factor = (Decimal("100") - value) / Decimal("100")
            return self._money(base * factor)

        # Fixed KES off
        return self._money(max(base - value, Decimal("0")))

    # ------------------------------------------------------------------
    # Persistence Redis + DB
    # ------------------------------------------------------------------

    def _persist_open_quote(
        self,
        *,
        user,
        route_name: str,
        base_fare: Decimal,
        discounted_fare: Decimal,
        promo_code: Optional[str],
        promo_applied: bool,
        promo_reject_reason: Optional[str],
    ) -> FareQuote:
        now = timezone.now()
        expires = now + QUOTE_TTL
        qid = uuid.uuid4()

        with transaction.atomic():
            prior = FareQuote.objects.select_for_update().filter(
                user=user,
                status=FareQuote.Status.OPEN,
            )
            for old in prior:
                old.status = FareQuote.Status.ABANDONED
                old.save(update_fields=["status", "updated_at"])
                self._redis_delete_quote(old)

            quote = FareQuote.objects.create(
                quote_id=qid,
                user=user,
                route_name=route_name,
                base_fare=base_fare,
                discounted_fare=discounted_fare,
                promo_code=promo_code,
                promo_applied=promo_applied,
                promo_reject_reason=promo_reject_reason,
                status=FareQuote.Status.OPEN,
                expires_at=expires,
            )

        self._redis_write_quote(quote)
        return quote

    def _redis_write_quote(self, quote: FareQuote) -> None:
        payload = {
            "quote_id": str(quote.quote_id),
            "user_id": quote.user_id,
            "route_name": quote.route_name,
            "base_fare": str(quote.base_fare),
            "discounted_fare": str(quote.discounted_fare),
            "promo_code": quote.promo_code,
            "promo_applied": quote.promo_applied,
            "status": quote.status,
            "expires_at": quote.expires_at.isoformat(),
        }
        ttl = max(int((quote.expires_at - timezone.now()).total_seconds()), 1)
        key = REDIS_KEY_PREFIX + str(quote.quote_id)
        try:
            self.redis.setex(key, ttl, json.dumps(payload))
            if quote.user_id:
                self.redis.setex(
                    REDIS_USER_LATEST_PREFIX + str(quote.user_id),
                    ttl,
                    str(quote.quote_id),
                )
        except redis.RedisError as exc:
            logger.warning("FareQuote Redis write failed quote_id=%s err=%s", quote.quote_id, exc)

    def _redis_delete_quote(self, quote: FareQuote) -> None:
        self._redis_delete_keys(str(quote.quote_id), quote.user_id)

    def _redis_delete_keys(self, quote_id: str, user_id: Optional[int]) -> None:
        try:
            self.redis.delete(REDIS_KEY_PREFIX + quote_id)
            if user_id:
                latest_key = REDIS_USER_LATEST_PREFIX + str(user_id)
                current = self.redis.get(latest_key)
                if current == quote_id:
                    self.redis.delete(latest_key)
        except redis.RedisError as exc:
            logger.warning("FareQuote Redis delete failed quote_id=%s err=%s", quote_id, exc)

    def _get_open_quote_or_raise(self, quote_id: Union[str, uuid.UUID]) -> FareQuote:
        quote = FareQuote.objects.filter(quote_id=self._as_uuid(quote_id)).first()
        if quote is None:
            # Fallback Redis (DB miss) — still require DB for payment authority
            raise FareQuoteError(f"Quote {quote_id} not found in DB")

        if quote.status != FareQuote.Status.OPEN:
            raise FareQuoteError(f"Quote {quote_id} is not OPEN (status={quote.status})")

        if quote.expires_at <= timezone.now():
            self.monitor_and_expire_open_quotes()
            raise FareQuoteError(f"Quote {quote_id} has expired")

        if quote.discounted_fare is None or quote.discounted_fare < 0:
            raise FareQuoteError(f"Quote {quote_id} has invalid discounted_fare")
        if quote.base_fare is None:
            raise FareQuoteError(f"Quote {quote_id} has null base_fare")

        return quote

    def _copy_pricing_to_booking(self, booking: Booking, quote: FareQuote) -> None:
        booking.base_fare = quote.base_fare
        booking.discounted_fare = quote.discounted_fare
        booking.promo_code = quote.promo_code
        booking.fare_quote_id = quote.quote_id
        booking.save(
            update_fields=[
                "base_fare",
                "discounted_fare",
                "promo_code",
                "fare_quote_id",
                "updated_at",
            ]
        )

    # ------------------------------------------------------------------
    # Money helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_money(value: Union[int, float, Decimal, str], field: str = "amount") -> Decimal:
        try:
            d = Decimal(str(value))
        except Exception as exc:
            raise FareQuoteError(f"{field} is not a valid number") from exc
        if d != d:  # NaN
            raise FareQuoteError(f"{field} is NaN")
        return FareQuoteService._money(d)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _as_uuid(value: Union[str, uuid.UUID]) -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except Exception as exc:
            raise FareQuoteError(f"Invalid quote_id: {value}") from exc
