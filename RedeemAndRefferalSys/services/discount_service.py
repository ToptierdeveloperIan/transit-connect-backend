from django.db import transaction
from django.utils import timezone

from RedeemAndRefferalSys.exceptions import RedeemError
from RedeemAndRefferalSys.models import DiscountCode
from RedeemAndRefferalSys.policy import is_time_valid, mark_expired, should_revoke


class DiscountService:
    """
    Promo lifecycle (account side).

    redeem_to_account / activate_code:
      CREATED → REDEEMED  (couple to user; sets redeemed_at)

    Spend after payment is NOT here — use Checkout.consume_discount or
    utils.decrement_promo_attempt on RESERVED codes.
    """

    def activate_code(self, code: str, user):
        """
        Redemption: couple code to the user's account.

        CREATED → REDEEMED (+ redeemed_by_user, redeemed_at).
        Idempotent if already REDEEMED by the same user.
        """
        now = timezone.now()

        with transaction.atomic():
            obj = (
                DiscountCode.objects.select_for_update()
                .filter(code=code)
                .first()
            )

            if not obj:
                raise RedeemError("Code not found.", code="not_found", status_code=404)

            # Already coupled to this user
            if obj.status == DiscountCode.Status.REDEEMED:
                if obj.redeemed_by_user_id == user.id:
                    if not is_time_valid(obj, now):
                        mark_expired(obj)
                        raise RedeemError(
                            "Code claim window or shelf life has expired.",
                            code="expired",
                            status_code=410,
                        )
                    return obj, True
                raise RedeemError(
                    "Code has already been redeemed by another account.",
                    code="already_redeemed",
                    status_code=409,
                )

            if obj.status == DiscountCode.Status.USED:
                raise RedeemError(
                    "Code has already been used (attempts exhausted).",
                    code="already_used",
                    status_code=409,
                )

            if obj.status == DiscountCode.Status.REVOKED:
                raise RedeemError("Code has been revoked.", code="revoked", status_code=409)

            if obj.status == DiscountCode.Status.EXPIRED:
                raise RedeemError("Code has expired.", code="expired", status_code=410)

            if obj.status == DiscountCode.Status.RESERVED:
                raise RedeemError(
                    "Code is reserved for a checkout in progress.",
                    code="reserved",
                    status_code=409,
                )

            if obj.status != DiscountCode.Status.CREATED:
                raise RedeemError(
                    "Code is not available for redemption.",
                    code="invalid_status",
                    status_code=409,
                )

            # Shelf life before first redemption
            if should_revoke(
                obj.expires_at,
                now,
                obj.status,
                created_at=obj.created_at,
                redeemed_at=None,
            ):
                mark_expired(obj)
                raise RedeemError(
                    "Code shelf life has expired.",
                    code="expired",
                    status_code=410,
                )

            obj.status = DiscountCode.Status.REDEEMED
            obj.redeemed_at = now
            obj.redeemed_by_user = user
            obj.save(update_fields=["status", "redeemed_at", "redeemed_by_user"])

            return obj, False

    def redeem_code(self, code: str, user):
        """
        DEPRECATED for payment spend.

        Do not use this to mark USED. Canonical spend:
          REDEEMED → RESERVED (checkout) → USED (after payment success).

        Kept as a hard error so callers fail loudly.
        """
        raise RedeemError(
            "redeem_code is deprecated for spend. "
            "Redeem to account via activate_code; spend via checkout reserve + "
            "payment success consume.",
            code="deprecated_spend_path",
            status_code=400,
        )
