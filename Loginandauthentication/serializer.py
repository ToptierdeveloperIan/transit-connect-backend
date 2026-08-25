
import re
from .models import CustomUser, ToBeNotified_Email
from rest_framework import serializers


class AndroidOtpRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

class RegisterUserSerializers(serializers.ModelSerializer):
    verificationMethod = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'phone_number',
            'first_name',
            'second_name',
            'verificationMethod',
            'email'
        ]

    def create(self, validated_data):
        # 🔥 REMOVE FIELDS THAT ARE NOT IN THE MODEL
        validated_data.pop('verificationMethod', None)
        validated_data.pop('email', None)

        user = CustomUser.objects.create_user(
            phone_number=validated_data['phone_number'],
            first_name=validated_data['first_name'],
            second_name=validated_data['second_name'],
        )
        return user


from rest_framework import serializers
import re

class OtpVerificationSerializers(serializers.Serializer):
    phone_number = serializers.CharField(max_length=10)
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        otp_code = attrs.get("otp")

        # --- Validate phone number format ---
        if not re.match(r'^07\d{8}$', phone_number):
            raise serializers.ValidationError({"phone_number": "Phone number must be 10 digits starting with 07"})

        # --- Validate OTP format ---
        if not re.match(r'^\d{6}$', otp_code):
            raise serializers.ValidationError({"otp": "OTP must be exactly 6 digits"})

        return attrs

class EmailNotificationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()  # Automatically validates email format

    class Meta:
        model = ToBeNotified_Email
        fields = ['email']


class ResendOtpSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

