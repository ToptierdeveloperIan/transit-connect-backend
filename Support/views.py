from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Support.serializers import (
    LegalAcceptRequestSerializer,
    LegalAcceptanceSerializer,
    LegalDocumentSerializer,
)
from Support.services.legal_service import LegalError, LegalService


def _error_response(exc: LegalError) -> Response:
    return Response(
        {
            "success": False,
            "error": exc.code,
            "message": exc.message,
        },
        status=exc.status,
    )


class SupportHealthView(APIView):
    """Confirms the Support app is mounted and reachable."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "success": True,
                "app": "Support",
                "message": "Support app is live.",
            }
        )


class CurrentTermsView(APIView):
    """
    GET /api/support/terms/?locale=en|sw

    Public: returns the current published Terms of Service for the locale
    (falls back to English if the locale is missing).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        locale = request.query_params.get("locale")
        try:
            doc = LegalService.get_current_document(
                document_type="TERMS",
                locale=locale,
            )
        except LegalError as exc:
            return _error_response(exc)

        return Response(
            {
                "success": True,
                "message": "Current terms retrieved.",
                "data": LegalDocumentSerializer(doc).data,
            }
        )


class TermsStatusView(APIView):
    """
    GET /api/support/terms/status/

    Authenticated: whether the user must accept the current TERMS version.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            status_dto = LegalService.get_status(request.user, document_type="TERMS")
        except LegalError as exc:
            return _error_response(exc)

        return Response(
            {
                "success": True,
                "message": "Terms acceptance status retrieved.",
                "data": {
                    "document_type": status_dto.document_type,
                    "current_version": status_dto.current_version,
                    "accepted_version": status_dto.accepted_version,
                    "must_accept": status_dto.must_accept,
                    "accepted_at": status_dto.accepted_at,
                },
            }
        )


class AcceptTermsView(APIView):
    """
    POST /api/support/terms/accept/

    Body: { version, locale?, platform?, app_version? }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = LegalAcceptRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            acceptance = LegalService.accept(
                request.user,
                version=data["version"],
                locale=data.get("locale"),
                document_type=data.get("document_type") or "TERMS",
                platform=data.get("platform") or "",
                app_version=data.get("app_version") or "",
            )
        except LegalError as exc:
            return _error_response(exc)

        return Response(
            {
                "success": True,
                "message": "Terms accepted.",
                "data": LegalAcceptanceSerializer(acceptance).data,
            },
            status=status.HTTP_200_OK,
        )


class CurrentLegalDocumentView(APIView):
    """
    Extensible alias: GET /api/support/legal/current/?document_type=TERMS&locale=sw
    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            doc = LegalService.get_current_document(
                document_type=request.query_params.get("document_type"),
                locale=request.query_params.get("locale"),
            )
        except LegalError as exc:
            return _error_response(exc)

        return Response(
            {
                "success": True,
                "message": "Current legal document retrieved.",
                "data": LegalDocumentSerializer(doc).data,
            }
        )
