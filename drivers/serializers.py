import re
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from Loginandauthentication.models import CustomUser
from Loginandauthentication.finalOTP import OTP
from Loginandauthentication.whatsappOTP import normalize_phone_number


class PhoneTokenObtainPairSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        # ---- Normalize inputs ----
        raw_phone = attrs.get("phone_number")
        otp_code = attrs.get("otp")

        phone_number = normalize_phone_number(raw_phone)

        # ---- Validate phone format (after normalization) ----
        if not re.match(r'^\+?\d{10,15}$', phone_number):
            raise serializers.ValidationError({
                "phone_number": "Invalid phone number format"
            })

        # ---- Validate OTP format ----
        if not re.match(r'^\d{6}$', otp_code):
            raise serializers.ValidationError({
                "otp": "OTP must be exactly 6 digits"
            })

        # ---- Verify OTP (ANDROID FLOW) ----
        otp_result = OTP.android_verify_otp(phone_number, otp_code)

        if not otp_result or otp_result.get("code") != 200:
            raise serializers.ValidationError({
                "otp": otp_result.get("message", "Invalid or expired OTP")
            })

        # ---- Fetch existing user ONLY ----
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError({
                "phone_number": "User not registered"
            })

        # ---- Issue JWT ----
        refresh = RefreshToken.for_user(user)

        # ---- Final response ----
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user_id": user.id,
            "is_driver": user.is_driver,
            "first_name": user.first_name,
            "second_name": user.second_name,
            "phone_number": user.phone_number,
        }
