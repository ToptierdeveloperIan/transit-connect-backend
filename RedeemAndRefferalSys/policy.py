"""
Promo time + expiry policy (RedeemAndRefferalSys).

Clocks
------
1. Creation shelf life:  created_at + SHELF_LIFE  (default 3 months)
2. Claim window:         redeemed_at + CLAIM_WINDOW  (default 2 weeks after redemption)

Redemption = couple code to user account (status REDEEMED), not payment.
USED = attempts deducted after payment — do not use USED for timer expiry.

See PROMO_LIFECYCLE.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from .models import DiscountCode

# Tunable product constants
SHELF_LIFE = timedelta(days=90)  # ~3 months from creation
CLAIM_WINDOW = timedelta(weeks=2)  # from redemption (account couple); subject to change


def shelf_expires_at(creation_timestamp: datetime) -> datetime:
    """
    Absolute expiry from mint time: creation + 3 months.
    Call at mint to set DiscountCode.expires_at (optional override by admin).
    """
    return creation_timestamp + SHELF_LIFE


# Back-compat name used in older notes
def exp_logic(creation_timestamp: datetime) -> datetime:
    return shelf_expires_at(creation_timestamp)


def claim_expires_at(redemption_timestamp: datetime) -> datetime:
    """
    Entitlement window after redemption (user gained the code object).
    redeemed_at + 2 weeks (subject to change).
    """
    return redemption_timestamp + CLAIM_WINDOW


# Back-compat name
def revocation_logic_after_redemption(redemption_timestamp: datetime) -> datetime:
    return claim_expires_at(redemption_timestamp)


def should_expire_by_shelf(
    created_at: Optional[datetime],
    expires_at: Optional[datetime],
    current_timestamp: Optional[datetime] = None,
) -> bool:
    """True if absolute shelf life has passed."""
    now = current_timestamp or timezone.now()
    deadline = expires_at
    if deadline is None and created_at is not None:
        deadline = shelf_expires_at(created_at)
    if deadline is None:
        return False
    return now > deadline


def should_expire_by_claim_window(
    redeemed_at: Optional[datetime],
    current_timestamp: Optional[datetime] = None,
) -> bool:
    """
    True if claim window after redemption has passed.
    Only applies once the code has been redeemed (redeemed_at set).
    """
    if redeemed_at is None:
        return False
    now = current_timestamp or timezone.now()
    return now > claim_expires_at(redeemed_at)


def should_revoke(
    exp_timestamp: Optional[datetime],
    current_timestamp: Optional[datetime],
    status: str,
    *,
    created_at: Optional[datetime] = None,
    redeemed_at: Optional[datetime] = None,
) -> bool:
    """
    Whether the code should leave the usable pool due to **time** (→ EXPIRED).

    Does NOT apply to USED (attempts already spent) or already EXPIRED/REVOKED.

    Usable / mid-flight statuses that can expire:
      CREATED, REDEEMED, RESERVED

    Rules:
      - Shelf: now > expires_at (or created_at + 3 months if expires_at null)
      - Claim: if redeemed_at set, now > redeemed_at + 2 weeks
    """
    if status in (
        DiscountCode.Status.USED,
        DiscountCode.Status.EXPIRED,
        DiscountCode.Status.REVOKED,
    ):
        return False

    now = current_timestamp or timezone.now()

    if should_expire_by_shelf(created_at, exp_timestamp, now):
        return True
    if should_expire_by_claim_window(redeemed_at, now):
        return True
    return False


def is_time_valid(discount: DiscountCode, current_timestamp: Optional[datetime] = None) -> bool:
    """True if neither shelf nor claim window has killed this code."""
    return not should_revoke(
        discount.expires_at,
        current_timestamp,
        discount.status,
        created_at=discount.created_at,
        redeemed_at=discount.redeemed_at,
    )


def mark_expired(discount: DiscountCode, save: bool = True) -> DiscountCode:
    """Set status EXPIRED (time policy). Not USED."""
    discount.status = DiscountCode.Status.EXPIRED
    if save:
        discount.save(update_fields=["status"])
    return discount
