import re

from rest_framework import serializers


class RedeemCodeValidationSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=8, min_length=8, trim_whitespace=True)

    def validate_code(self, value):
        code = value.upper()
        if not re.fullmatch(r"[A-Z0-9]{8}", code):
            raise serializers.ValidationError("Code must be exactly 8 alphanumeric characters.")
        return code
