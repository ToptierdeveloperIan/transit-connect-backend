from rest_framework import serializers

from Support.models import LegalAcceptance, LegalDocument


class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = (
            "document_type",
            "version",
            "locale",
            "title",
            "body",
            "body_format",
            "effective_at",
            "updated_at",
        )
        read_only_fields = fields


class LegalAcceptRequestSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=32)
    locale = serializers.CharField(max_length=16, required=False, default="en")
    document_type = serializers.CharField(max_length=32, required=False, default="TERMS")
    platform = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    app_version = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class LegalAcceptanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalAcceptance
        fields = (
            "document_type",
            "version",
            "locale",
            "accepted_at",
            "platform",
            "app_version",
        )
        read_only_fields = fields
