"""
HTTP adapters for UserSettings.

All business rules live in services; this module only maps request/response.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from UserSettings.serializers import (
    PhoneConfirmSerializer,
    PhoneRequestSerializer,
    UpdateNameSerializer,
)
from UserSettings.services.exceptions import SettingsError
from UserSettings.services.phone_change_service import PhoneChangeService
from UserSettings.services.profile_service import ProfileService


def _ok(message: str, data, status_code=status.HTTP_200_OK):
    return Response({"success": True, "message": message, "data": data}, status=status_code)


def _err(exc: SettingsError):
    return Response(
        {"success": False, "error": exc.code, "message": exc.message},
        status=exc.status,
    )


class UserSettingsHealthView(APIView):
    """Mount check for the UserSettings app."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "success": True,
                "app": "UserSettings",
                "message": "UserSettings app is live.",
            }
        )


class ProfileDetailView(APIView):
    """
    GET /api/settings/profile/

    Authoritative snapshot for Settings UI and Room prefill (includes profile_version).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = ProfileService.get_profile_snapshot(request.user)
        return _ok("Profile retrieved.", data)


class UpdateNameView(APIView):
    """
    PATCH /api/settings/profile/name/

    Online path and offline-queue replay path share this endpoint.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        ser = UpdateNameSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            data = ProfileService.update_name(
                request.user,
                first_name=d["first_name"],
                second_name=d["second_name"],
                mutation_id=d["mutation_id"],
                base_version=d.get("base_version"),
            )
        except SettingsError as exc:
            return _err(exc)
        return _ok("Name updated.", data)


class PhoneChangeRequestView(APIView):
    """
    POST /api/settings/profile/phone/request/

    Online only. Sends OTP to the new number; does not commit phone yet.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PhoneRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            data = PhoneChangeService.request_change(
                request.user,
                new_phone_number=d["new_phone_number"],
                mutation_id=d["mutation_id"],
            )
        except SettingsError as exc:
            return _err(exc)
        return _ok("Verification code sent to the new number.", data)


class PhoneChangeConfirmView(APIView):
    """
    POST /api/settings/profile/phone/confirm/

    Commits phone_number only after OTP succeeds.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PhoneConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            data = PhoneChangeService.confirm_change(
                request.user,
                challenge_id=d["challenge_id"],
                otp=d["otp"],
                mutation_id=d["mutation_id"],
            )
        except SettingsError as exc:
            return _err(exc)
        return _ok("Phone number updated.", data)
