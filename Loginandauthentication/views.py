from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .models import CustomUser
from .whatsappOTP import  normalize_phone_number
from rest_framework.response import Response

from rest_framework import status
import json

from .finalOTP import OTP
from .serializer import RegisterUserSerializers, OtpVerificationSerializers, EmailNotificationSerializer, \
    ResendOtpSerializer, AndroidOtpRequestSerializer
from .finalOTP import r


class AndroidRequestOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AndroidOtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print(request.data)

        phone_number = normalize_phone_number(
            serializer.validated_data["phone_number"]
        )
        print(phone_number)

        # ✅ CHECK USER EXISTS
        if not CustomUser.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ GENERATE & SEND OTP (ANDROID FLOW)
        result = OTP.android_generate_and_send_otp(phone_number)

        return Response(
            result,
            status=status.HTTP_200_OK
        )

class EarlyRegisterUserView(APIView):
    permission_classes = (AllowAny,)
    def post(self, request):
        serializer = RegisterUserSerializers(data=request.data)
        print(request.data)
        if serializer.is_valid():
            OTP.save_user_otp(serializer.validated_data)
            return Response({"message": "OTP sent"}, status=status.HTTP_200_OK)
        else:
            print(serializer.errors)  # <- add this
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class PostOtpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        otpserializer = OtpVerificationSerializers(data=request.data)
        otpserializer.is_valid(raise_exception=True)

        phone_number = otpserializer.validated_data["phone_number"]
        otp_code = otpserializer.validated_data["otp"]

        # Verify OTP
        result = OTP.verify_otp(phone_number, otp_code)
        if result["code"] != 200:
            return Response(result, status=result["code"])

        # OTP verified → fetch registration data from Redis
        stored_data = json.loads(r.get(f"user_otp:{phone_number}") or '{}')
        stored_data.pop("otp", None)
        stored_data.pop("verification_channel", None)
        stored_data.pop("email", None)
        if not stored_data:
            return Response({"message": "Registration data not found"}, status=404)

        # Create serializer and save model
        user_serializer = RegisterUserSerializers(data=stored_data)
        user_serializer.is_valid(raise_exception=True)
        user_serializer.save()

        return Response({"message": "User registered successfully"}, status=200)


class to_be_notified_email(APIView):
    def post(self, request):
        serializer = EmailNotificationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResendOtpView(APIView):
    def post(self, request):
        print(request.data)
        phone_number = request.data.get("phone_number")
        if not phone_number:
            return Response({"detail": "Phone number is required"}, status=400)

        result = OTP.resend_otp(phone_number)

        if result["success"]:
            return Response({"detail": result["message"]}, status=200)
        else:
            return Response({"detail": result["message"]}, status=400)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print("DATA RECEIVED:", request.data)

        raw_phone = request.data.get("phone_number")
        otp_code = request.data.get("otp")

        if not raw_phone or not otp_code:
            return Response(
                {"message": "Phone number and OTP are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = normalize_phone_number(raw_phone)

        # 1️⃣ Verify OTP (DO NOT delete Redis here)
        result = OTP.verify_otp(phone_number, otp_code)
        if result["code"] != 200:
            return Response(result, status=result["code"])

        # 2️⃣ Fetch registration data from Redis
        redis_key = f"user_otp:{phone_number}"
        stored_data_json = r.get(redis_key)

        if not stored_data_json:
            return Response(
                {"message": "Registration data not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        stored_data = json.loads(stored_data_json)

        # 3️⃣ Create user DIRECTLY (no serializer)
        try:
             CustomUser.objects.create_user(
                phone_number=stored_data["phone_number"],
                first_name=stored_data.get("first_name", ""),
                second_name=stored_data.get("second_name", ""),
            )

        except Exception as e:
            print("USER CREATE ERROR:", e)
            return Response(
                {"error": "User creation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 4️⃣ Delete Redis ONLY after success
        r.delete(redis_key)

        return Response(
            {"message": "User registered successfully"},
            status=status.HTTP_200_OK
        )