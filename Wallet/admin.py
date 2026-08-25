from django.contrib import admin

from Wallet.models import LedgerEntry, WalletAccount, WalletIntent


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "available_balance",
        "held_balance",
        "currency",
        "is_active",
        "updated_at",
    )
    search_fields = ("user__phone_number", "user__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WalletIntent)
class WalletIntentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "wallet",
        "kind",
        "status",
        "channel",
        "amount",
        "provider_reference",
        "fare_quote_id",
        "created_at",
    )
    list_filter = ("kind", "status", "channel")
    search_fields = ("idempotency_key", "provider_reference")
    readonly_fields = ("id", "created_at", "updated_at", "succeeded_at")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """Read-only in spirit: do not edit amounts in admin."""

    list_display = (
        "id",
        "wallet",
        "entry_type",
        "amount",
        "balance_after",
        "channel",
        "provider_reference",
        "created_at",
    )
    list_filter = ("entry_type", "channel")
    search_fields = ("provider_reference", "description")
    readonly_fields = (
        "id",
        "wallet",
        "entry_type",
        "amount",
        "currency",
        "intent",
        "related_entry",
        "channel",
        "provider_reference",
        "description",
        "metadata",
        "balance_after",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
