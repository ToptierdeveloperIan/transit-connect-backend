"""
Django admin for promo DiscountCode minting and ops.

Design space (connects to utils / lifecycle — do not invent parallel rules):

  Mint / economics
    → utils.discount_code_generator(max_attempts=..., value=...)
    → utils.set_promo_code_economics(...)
    → utils.build_promo_mint_fields(...)

  Identity
    → DiscountCode.created_by = admin user on create

  Shelf clock
    → policy.shelf_expires_at (default if expires_at empty)

  Force kill
    → status REVOKED (not USED)

  Do NOT from admin:
    → mark USED (payment path only)
    → DiscountService.redeem_code (deprecated spend)
    → couple redeemed_by_user (rider redeem API)

See PROMO_ADMIN.md and PROMO_LIFECYCLE.md.
"""

from __future__ import annotations

import random
import string

from django.contrib import admin, messages
from django.utils import timezone

from .models import DiscountCode
from .policy import shelf_expires_at
from .utils import (
    PromoConfigError,
    discount_code_generator,
    set_promo_code_economics,
)


def _unique_promo_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(chars, k=length))
        if not DiscountCode.objects.filter(code=code).exists():
            return code


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    """
    Admin owns mint + configure + revoke.
    Lifecycle after REDEEMED is system/checkout/payment.
    """

    list_display = (
        "code",
        "status",
        "value",
        "allowed_attempts",
        "expires_at",
        "redeemed_by_user",
        "created_by",
        "created_at",
        "redeemed_at",
    )
    list_filter = ("status", "created_at", "expires_at")
    search_fields = ("code", "redeemed_by_user__username", "created_by__username")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    readonly_fields = (
        "created_at",
        "redeemed_at",
        "redeemed_by_user",
        "last_synced_at",
    )

    fieldsets = (
        (
            "Code",
            {
                "fields": ("code", "status"),
                "description": (
                    "Leave code blank on add to auto-generate a unique 8-char code. "
                    "Prefer status CREATED for new promos."
                ),
            },
        ),
        (
            "Economics (admin mint)",
            {
                "fields": ("value", "Value_of_code", "allowed_attempts"),
                "description": (
                    "Set max attempts >= 1 and value before riders redeem. "
                    "On save for CREATED codes, set_promo_code_economics keeps "
                    "value and Value_of_code in sync."
                ),
            },
        ),
        (
            "Clocks",
            {
                "fields": ("expires_at", "created_at", "redeemed_at"),
                "description": (
                    "expires_at defaults to now + 3 months (shelf life) if left empty. "
                    "redeemed_at is set when a rider redeems to their account (not admin)."
                ),
            },
        ),
        (
            "People",
            {
                "fields": ("created_by", "redeemed_by_user"),
            },
        ),
        (
            "Other",
            {
                "fields": ("metadata", "last_synced_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = (
        "action_mint_five_single_use",
        "action_revoke_selected",
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is None:
            return readonly
        if obj.status != DiscountCode.Status.CREATED:
            readonly = list(
                set(readonly)
                | {
                    "code",
                    "redeemed_by_user",
                    "redeemed_at",
                    "created_by",
                }
            )
        return readonly

    def save_model(self, request, obj, form, change):
        """
        Admin create/update:

        - New + empty code → auto unique code
        - created_by on first save
        - expires_at default from shelf policy
        - CREATED + attempts >= 1 → set_promo_code_economics
        """
        is_new = obj.pk is None

        if is_new:
            if not obj.created_by_id:
                obj.created_by = request.user
            if not (obj.code or "").strip():
                obj.code = _unique_promo_code()
            if not obj.status:
                obj.status = DiscountCode.Status.CREATED
            if not obj.expires_at:
                obj.expires_at = shelf_expires_at(timezone.now())

        super().save_model(request, obj, form, change)

        if obj.status == DiscountCode.Status.CREATED:
            try:
                attempts = obj.allowed_attempts if obj.allowed_attempts and obj.allowed_attempts >= 1 else 1
                set_promo_code_economics(
                    obj,
                    max_attempts=int(attempts),
                    value=obj.value if obj.value is not None else 0,
                    save=True,
                )
                if is_new:
                    messages.success(
                        request,
                        f"Promo {obj.code} saved (attempts={obj.allowed_attempts}, "
                        f"value={obj.value}, expires={obj.expires_at}).",
                    )
            except PromoConfigError as exc:
                messages.warning(request, f"Economics not applied: {exc}")

    @admin.action(description="Mint 5 single-use promos (1 attempt, value=10)")
    def action_mint_five_single_use(self, request, queryset):
        """
        Batch mint via discount_code_generator — ignores selection.
        Uses product mint helper (CREATED + shelf expires_at + economics).
        """
        created_codes = []
        for _ in range(5):
            promo = discount_code_generator(max_attempts=1, value=10)
            promo.created_by = request.user
            promo.save(update_fields=["created_by"])
            created_codes.append(promo.code)
        self.message_user(
            request,
            f"Minted {len(created_codes)} codes via discount_code_generator: "
            f"{', '.join(created_codes)}",
            messages.SUCCESS,
        )

    @admin.action(description="Revoke selected (force REVOKED — not USED)")
    def action_revoke_selected(self, request, queryset):
        """
        Admin force-kill. Does not mark USED (payment-only).
        Skips already USED.
        """
        qs = queryset.exclude(status=DiscountCode.Status.USED)
        count = qs.update(status=DiscountCode.Status.REVOKED)
        skipped = queryset.filter(status=DiscountCode.Status.USED).count()
        msg = f"Revoked {count} promo(s)."
        if skipped:
            msg += f" Skipped {skipped} USED code(s) (attempts already spent)."
        self.message_user(request, msg, messages.SUCCESS)
