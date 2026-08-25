from rest_framework import status
from rest_framework.response import Response

from .utils import get_or_create_version, parse_since_param


class DeltaSyncMixin:
    def filter_since(self, queryset):
        since = self.request.query_params.get("since")
        if not since:
            return queryset
        parsed_since = parse_since_param(since)
        return queryset.filter(updated_at__gt=parsed_since)


class ConflictDetectionMixin:
    conflict_message = "Your local data is stale. Fetch the latest version before updating."

    def get_resource_type(self):
        return self.resource_type

    def get_resource_id(self):
        return None

    def check_conflict(self):
        client_version = self.request.headers.get("X-Client-Version")
        if client_version is None:
            return None

        try:
            client_version = int(client_version)
        except (TypeError, ValueError):
            return Response(
                {"error": "invalid_version", "message": "X-Client-Version must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        version = get_or_create_version(self.get_resource_type(), self.get_resource_id())
        if client_version < version.version:
            return Response(
                {
                    "error": "conflict",
                    "message": self.conflict_message,
                    "server_version": version.version,
                    "client_version": client_version,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return None


class ETagResponseMixin:
    def add_version_headers(self, response, resource_type, resource_id=None):
        version = get_or_create_version(resource_type, resource_id)
        response["X-Resource-Type"] = resource_type
        response["X-Resource-Version"] = str(version.version)
        response["X-Resource-Updated-At"] = version.updated_at.isoformat()
        return response
