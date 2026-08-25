from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ride_matching.models import Booking, Route

from .mixins import ConflictDetectionMixin, DeltaSyncMixin, ETagResponseMixin
from .serializers import (
    BookingSyncSerializer,
    ProfileSyncSerializer,
    ResourceVersionSerializer,
    RouteSyncSerializer,
)
from .utils import get_or_create_version


def success_response(message, data, count=None, status_code=status.HTTP_200_OK):
    payload = {
        "success": True,
        "message": message,
        "data": data,
    }
    if count is not None:
        payload["count"] = count
    return Response(payload, status=status_code)


class SyncManifestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        versions = [
            get_or_create_version("routes"),
            get_or_create_version("profile", request.user.pk),
            get_or_create_version("bookings", request.user.pk),
        ]
        data = ResourceVersionSerializer(versions, many=True).data
        return success_response("Sync manifest retrieved.", data, count=len(data))


class ProfileSyncView(ConflictDetectionMixin, ETagResponseMixin, APIView):
    permission_classes = [IsAuthenticated]
    resource_type = "profile"

    def get_resource_id(self):
        return self.request.user.pk

    def get(self, request):
        data = ProfileSyncSerializer(request.user).data
        response = success_response("Profile sync data retrieved.", data, count=1)
        return self.add_version_headers(response, "profile", request.user.pk)

    def patch(self, request):
        """
        Generic profile PATCH for non-identity fields only.

        first_name, second_name, phone_number, email MUST go through
        UserSettings (/api/settings/...) so offline queue + OTP policies stay
        single-writer and cannot conflict with this endpoint.
        """
        blocked = {
            "first_name",
            "second_name",
            "phone_number",
            "email",
            "phone",
            "firstName",
            "secondName",
        }
        illegal = blocked.intersection(set(request.data.keys()))
        if illegal:
            return Response(
                {
                    "success": False,
                    "error": "use_settings_api",
                    "message": (
                        "Identity fields must be updated via /api/settings/profile/* "
                        f"(rejected keys: {sorted(illegal)})."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        conflict = self.check_conflict()
        if conflict:
            return conflict

        serializer = ProfileSyncSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        data = ProfileSyncSerializer(request.user).data
        response = success_response("Profile updated.", data, count=1)
        return self.add_version_headers(response, "profile", request.user.pk)


class RoutesSyncView(DeltaSyncMixin, ETagResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            queryset = self.filter_since(
                Route.objects.prefetch_related("destinations").order_by("id")
            )
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = RouteSyncSerializer(queryset, many=True).data
        response = success_response("Routes sync data retrieved.", data, count=len(data))
        return self.add_version_headers(response, "routes")


class BookingsSyncView(DeltaSyncMixin, ETagResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            queryset = self.filter_since(
                Booking.objects.filter(user=request.user)
                .select_related("bus", "bus__driver", "bus__driver__user", "route")
                .order_by("-timestamp")
            )
        except ValueError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        data = BookingSyncSerializer(queryset, many=True).data
        response = success_response("Bookings sync data retrieved.", data, count=len(data))
        return self.add_version_headers(response, "bookings", request.user.pk)
