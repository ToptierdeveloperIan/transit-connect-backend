from django.contrib import admin

from Support.models import LegalAcceptance, LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_type",
        "version",
        "locale",
        "title",
        "is_published",
        "effective_at",
        "updated_at",
    )
    list_filter = ("document_type", "locale", "is_published", "body_format")
    search_fields = ("version", "title", "body")
    ordering = ("-effective_at",)


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "document_type",
        "version",
        "locale",
        "accepted_at",
        "platform",
        "app_version",
    )
    list_filter = ("document_type", "locale", "platform")
    search_fields = ("user__phone_number", "version")
    readonly_fields = ("accepted_at",)
