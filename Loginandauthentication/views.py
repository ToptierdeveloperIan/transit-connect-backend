
from rest_framework.views import APIView
from .whatsappOTP import  normalize_phone_number
from rest_framework.response import Response

from rest_framework import status
import json

from .finalOTP import OTP
from .serializer import RegisterUserSerializers, OtpVerificationSerializers, EmailNotificationSerializer, \
    ResendOtpSerializer
from .finalOTP import r



class EarlyRegisterUserView(APIView):
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
    def post(self, request):
        print(request.data)
        unormalized_phone_number = request.data.get("phone_number")
        phone_number = normalize_phone_number(unormalized_phone_number)
        otp_code = request.data.get("otp")

        if not phone_number or not otp_code:
            return Response(
                {"message": "Phone number and OTP code are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Call your static method
        result = OTP.verify_otp(phone_number, otp_code)
        if not result:
            print("Error verfiying code")

        # Return appropriate response
        if result["code"] == 200:
            return Response(result, status=status.HTTP_200_OK)
        elif result["code"] == 404:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


