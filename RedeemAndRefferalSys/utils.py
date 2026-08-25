"""
Promo discount helpers (RedeemAndRefferalSys only — no referral).

Docs:
  → PROMO_LIFECYCLE.md  (state machine, redemption vs USED, two clocks)
  → PROMO_UTILS.md      (mint/attempt helper API)

State machine (DiscountCode.Status):
  CREATED → REDEEMED → RESERVED → USED
                    ↘ EXPIRED / REVOKED

  REDEEMED = user account couple (redemption), not payment.
  USED     = attempt deducted after payment success.
"""

from __future__ import annotations

import random
import string
from decimal import Decimal
from typing import Any, Optional, Union

from django.db import transaction

from .models import DiscountCode


# ---------------------------------------------------------------------------
# Errors (local to redeem utils — do not depend on other apps)
# ---------------------------------------------------------------------------

class PromoConfigError(ValueError):
    """Invalid mint / setter input."""


class PromoAttemptError(ValueError):
    """Attempt tracking failed (wrong code, zero remaining, bad status)."""


# ---------------------------------------------------------------------------
# 1) BEFORE / AT MINT — setters for max attempts + value
# ---------------------------------------------------------------------------

def build_promo_mint_fields(
    max_attempts: int,
    value: Union[int, float, Decimal, str],
) -> dict[str, Any]:
    """
    Call **before** DiscountCode.objects.create(...).

    Pure setter of mint economics: validates and returns field kwargs so create
    never leaves allowed_attempts=0 or an unset value by accident.

    Usage::

        fields = build_promo_mint_fields(max_attempts=1, value=20)
        DiscountCode.objects.create(code=code, status=CREATED, **fields)

    Returns:
        dict with allowed_attempts, value, Value_of_code (kept in sync).
    """
    attempts = _coerce_max_attempts(max_attempts)
    amount = _coerce_value(value)

    return {
        "allowed_attempts": attempts,
        "value": amount,
        "Value_of_code": amount,
    }


def set_promo_code_economics(
    discount: DiscountCode,
    max_attempts: int,
    value: Union[int, float, Decimal, str],
    *,
    save: bool = True,
) -> DiscountCode:
    """
    Setter: take max_attempts + value and **edit** an existing DiscountCode.

    Place this after a bare create (code + CREATED only) or when admin updates
    economics before the code is activated.

    Constrained rules:
      - max_attempts must be >= 1 (promo must be usable at least once)
      - value must be >= 0
      - writes both value and Value_of_code for consistency
      - does not change status, code string, or user binding

    Prefer status CREATED when configuring; mid-lifecycle edits should be rare.
    """
    if discount is None or not getattr(discount, "pk", None):
        raise PromoConfigError("set_promo_code_economics requires a saved DiscountCode instance.")

    attempts = _coerce_max_attempts(max_attempts)
    amount = _coerce_value(value)

    discount.allowed_attempts = attempts
    discount.value = amount
    discount.Value_of_code = amount

    if save:
        discount.save(update_fields=["allowed_attempts", "value", "Value_of_code"])

    return discount


def _coerce_max_attempts(max_attempts: int) -> int:
    try:
        n = int(max_attempts)
    except (TypeError, ValueError) as exc:
        raise PromoConfigError("max_attempts must be an integer.") from exc
    if n < 1:
        raise PromoConfigError(
            "max_attempts must be >= 1. Zero means the code can never be reserved at checkout."
        )
    return n


def _coerce_value(value: Union[int, float, Decimal, str]) -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise PromoConfigError("value must be a number.") from exc
    if amount < 0:
        raise PromoConfigError("value must be >= 0.")
    return amount


# ---------------------------------------------------------------------------
# 2) ATTEMPT TRACKING — remaining, zero, which code is decremented
# ---------------------------------------------------------------------------

def get_attempts_remaining(discount: DiscountCode) -> int:
    """
    How many checkout spends remain on this code.

    Field: DiscountCode.allowed_attempts (remaining budget, not a separate column).
    """
    if discount is None:
        return 0
    remaining = int(discount.allowed_attempts or 0)
    return max(remaining, 0)


def attempts_exhausted(discount: DiscountCode) -> bool:
    """True when remaining attempts are zero (cannot reserve/consume)."""
    return get_attempts_remaining(discount) <= 0


def assert_attempts_available(discount: DiscountCode) -> int:
    """
    Strict gate: raise if this code has no remaining attempts.

    Returns remaining count when > 0.
    """
    remaining = get_attempts_remaining(discount)
    if remaining <= 0:
        raise PromoAttemptError(
            f"Promo code {getattr(discount, 'code', '?')!r} has 0 attempts remaining; "
            "cannot reserve or consume."
        )
    return remaining


def resolve_promo_code(
    discount: Optional[DiscountCode] = None,
    *,
    code: Optional[str] = None,
    for_update: bool = False,
) -> DiscountCode:
    """
    Resolve exactly one DiscountCode row.

    KEY VARIABLE — which code is in play:
      - Prefer passing the DiscountCode instance you already loaded.
      - Or pass code= the 8-char string; lookup is case-normalized to upper.
      - If both are passed, the instance's code must match ``code`` or we raise
        (prevents decrementing a different row than the caller intended).

    for_update=True uses select_for_update (must be inside transaction.atomic).
    """
    if discount is None and not code:
        raise PromoAttemptError("Provide discount instance and/or code= string.")

    normalized = code.strip().upper() if code else None

    if discount is not None and normalized is not None:
        if discount.code.upper() != normalized:
            raise PromoAttemptError(
                f"Code mismatch: instance is {discount.code!r} but caller required {normalized!r}. "
                "Attempts are only ever subtracted from one explicit code row."
            )

    qs = DiscountCode.objects.all()
    if for_update:
        qs = qs.select_for_update()

    if discount is not None and discount.pk:
        locked = qs.filter(pk=discount.pk).first()
        if locked is None:
            raise PromoAttemptError("DiscountCode row not found for given instance.")
        if normalized is not None and locked.code.upper() != normalized:
            raise PromoAttemptError(
                f"Code mismatch after lock: row is {locked.code!r}, expected {normalized!r}."
            )
        return locked

    locked = qs.filter(code=normalized).first()
    if locked is None:
        raise PromoAttemptError(f"Promo code {normalized!r} not found.")
    return locked


def what_happens_when_attempts_are_zero(discount: DiscountCode) -> dict[str, Any]:
    """
    Documented behaviour snapshot when remaining attempts == 0.

    Rules:
      - Cannot reserve at checkout (Checkout validate_reserve_discount).
      - Cannot consume (no spend left).
      - Status should already be USED after the last successful payment consume;
        if still ACTIVE/RESERVED with 0 attempts, treat as unusable / data error.
    """
    remaining = get_attempts_remaining(discount)
    return {
        "code": discount.code,
        "attempts_remaining": remaining,
        "exhausted": remaining <= 0,
        "status": discount.status,
        "effects_when_zero": [
            "Reserve at checkout is rejected (allowed_attempts <= 0).",
            "Further decrement_promo_attempt calls raise PromoAttemptError.",
            "After last successful payment consume, status should be USED.",
            "Time expiry uses EXPIRED, not zero attempts.",
            "Rider should not see this promo as applicable for a new fare subsidy.",
        ],
    }


def decrement_promo_attempt(
    discount: Optional[DiscountCode] = None,
    *,
    code: Optional[str] = None,
    require_reserved: bool = True,
) -> DiscountCode:
    """
    Subtract **one** attempt from exactly one promo row.

    =========================================================================
    WHICH CODE IS DECREMENTED (strict)
    =========================================================================
    Only the row resolved by resolve_promo_code(discount=, code=):
      - Locked with select_for_update by primary key after resolve.
      - Optional code= must match that row or the call aborts.
      - Never decrements "any code for this user" or a queryset of many codes.
      - Never decrements a different code than the one identified above.

    =========================================================================
    WHEN TO CALL (canonical)
    =========================================================================
    After payment success, on a RESERVED code — same moment as Checkout
    consume_discount. Do not call on account redemption (CREATED→REDEEMED).

    require_reserved=True (default): status must be RESERVED before subtract.

    WHEN ATTEMPTS HIT ZERO → status USED (attempts exhausted).
    WHEN ATTEMPTS REMAIN   → status REDEEMED (still coupled; can reserve again).
    Does not overwrite redeemed_at (account-couple timestamp).
    """
    with transaction.atomic():
        locked = resolve_promo_code(discount, code=code, for_update=True)

        target_code = locked.code
        target_pk = locked.pk

        if require_reserved and locked.status != DiscountCode.Status.RESERVED:
            raise PromoAttemptError(
                f"Code {target_code!r} must be RESERVED before attempt decrement "
                f"(canonical path: after checkout hold, on payment success). "
                f"Current status={locked.status!r}."
            )

        remaining_before = get_attempts_remaining(locked)
        if remaining_before <= 0:
            raise PromoAttemptError(
                f"Code {target_code!r} (pk={target_pk}) has 0 attempts; refuse decrement."
            )

        locked.allowed_attempts = remaining_before - 1
        remaining_after = locked.allowed_attempts
        update_fields = ["allowed_attempts", "status"]

        if remaining_after <= 0:
            locked.allowed_attempts = 0
            locked.status = DiscountCode.Status.USED
        else:
            locked.status = DiscountCode.Status.REDEEMED

        locked.save(update_fields=update_fields)

        locked.refresh_from_db()
        if locked.pk != target_pk or locked.code != target_code:
            raise PromoAttemptError("Integrity failure: promo row identity changed during decrement.")

        return locked


# ---------------------------------------------------------------------------
# Generator — mint string + optional economics in one place
# ---------------------------------------------------------------------------

def discount_code_generator(
    length: int = 8,
    *,
    max_attempts: Optional[int] = None,
    value: Optional[Union[int, float, Decimal, str]] = None,
):
    """
    Generate a unique 8-char code and insert CREATED.

    Sets expires_at = created shelf life (3 months from now) on insert.
    If max_attempts and value are both provided, applies build_promo_mint_fields.
    """
    from django.utils import timezone

    from .policy import shelf_expires_at

    chars = string.ascii_uppercase + string.digits

    while True:
        code = "".join(random.choices(chars, k=length))
        if not DiscountCode.objects.filter(code=code).exists():
            break

    now = timezone.now()
    create_kwargs: dict[str, Any] = {
        "code": code,
        "status": DiscountCode.Status.CREATED,
        "expires_at": shelf_expires_at(now),
    }

    if max_attempts is not None and value is not None:
        create_kwargs.update(build_promo_mint_fields(max_attempts, value))
    elif max_attempts is not None or value is not None:
        raise PromoConfigError(
            "Pass both max_attempts and value together, or neither "
            "(then call set_promo_code_economics after create)."
        )

    return DiscountCode.objects.create(**create_kwargs)
