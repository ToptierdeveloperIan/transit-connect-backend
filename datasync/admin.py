from django.contrib import admin

from .models import ResourceVersion


@admin.register(ResourceVersion)
class ResourceVersionAdmin(admin.ModelAdmin):
    list_display = ("resource_type", "resource_id", "version", "updated_at")
    list_filter = ("resource_type",)
    search_fields = ("resource_type", "resource_id")
    readonly_fields = ("updated_at",)
