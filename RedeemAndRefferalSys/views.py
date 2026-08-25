from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import RedeemError
from .serializers import RedeemCodeValidationSerializer
from .services.discount_service import DiscountService


class RedeemCodeValidation(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RedeemCodeValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            discount_code, idempotent = DiscountService().activate_code(
                serializer.validated_data["code"],
                request.user,
            )
        except RedeemError as exc:
            return Response(
                {
                    "success": False,
                    "error": exc.code,
                    "message": exc.message,
                },
                status=exc.status_code,
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Code already redeemed on this account."
                    if idempotent
                    else "Code redeemed to your account successfully."
                ),
                "data": {
                    "code": discount_code.code,
                    "status": discount_code.status,
                    "value": str(discount_code.value),
                    "expires_at": discount_code.expires_at,
                    "redeemed_at": discount_code.redeemed_at,
                    "idempotent": idempotent,
                },
            }
        )
