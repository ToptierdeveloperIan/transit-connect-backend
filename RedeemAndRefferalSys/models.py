from django.conf import settings
from django.db import models


class DiscountCode(models.Model):
    """
    Promo discount code (not referral).

    State machine — see PROMO_LIFECYCLE.md and policy.py.

      CREATED  → REDEEMED  (redemption: couple to user account)
      REDEEMED → RESERVED  (checkout hold)
      RESERVED → USED      (payment success; attempt deducted)
      RESERVED → REDEEMED  (multi-use: attempts still remain)
      *        → EXPIRED   (time: claim window or shelf life)
      *        → REVOKED   (admin / force)

    USED  = attempts fully spent for this code's life (or last attempt used).
    REDEEMED = user owns the code object — not the same as USED.
    """

    class Status(models.TextChoices):
        # Minted by system/admin; not yet coupled to a rider account
        CREATED = "CREATED", "Created"
        # Redemption: coupled to redeemed_by_user; user may use it at checkout
        REDEEMED = "REDEEMED", "Redeemed"
        # Held for an in-flight checkout / payment
        RESERVED = "RESERVED", "Reserved"
        # Attempt(s) deducted after successful payment (not mere account couple)
        USED = "USED", "Used"
        # Failed time policy (creation shelf life or post-redemption claim window)
        EXPIRED = "EXPIRED", "Expired"
        # Forced invalidation (admin/system), distinct from natural EXPIRED
        REVOKED = "REVOKED", "Revoked"

    code = models.CharField(max_length=8, unique=True, db_index=True)

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )  # % or fixed amount — product must pick one meaning

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )

    Value_of_code = models.DecimalField(
        null=False, max_digits=100, decimal_places=2, default=0
    )
    allowed_attempts = models.IntegerField(null=False, default=0)

    # Clocks
    created_at = models.DateTimeField(auto_now_add=True)
    # Absolute shelf life (typically created_at + 3 months); null = not set yet
    expires_at = models.DateTimeField(null=True, blank=True)
    # When the user redeemed (coupled to account) — NOT when payment spent it
    redeemed_at = models.DateTimeField(null=True, blank=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)

    redeemed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="redeemed_discount_codes",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_discount_codes",
    )

    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.code
