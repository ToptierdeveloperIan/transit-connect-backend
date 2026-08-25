"""
HTTP surface for Wallet.

Business rules live in services. Callbacks from M-Pesa/Airtel should call
DepositService.apply_provider_success / failure (can be wired from paymentSystem).
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Wallet.serializers import DepositCreateSerializer, SpendCreateSerializer
from Wallet.services.deposit_service import DepositService
from Wallet.services.exceptions import WalletError
from Wallet.services.spend_service import SpendService
from Wallet.services.wallet_service import WalletService


def _ok(message, data, code=status.HTTP_200_OK):
    return Response({"success": True, "message": message, "data": data}, status=code)


def _err(exc: WalletError):
    return Response(
        {"success": False, "error": exc.code, "message": exc.message},
        status=exc.status,
    )


class WalletHealthView(APIView):
    """Mount check."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "success": True,
                "app": "Wallet",
                "message": "Wallet app is live.",
                "rails": ["MPESA", "AIRTEL"],
            }
        )


class WalletBalanceView(APIView):
    """GET /api/wallet/balance/ — available + held + spendable."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = WalletService.get_balance_snapshot(request.user)
        return _ok("Wallet balance retrieved.", data)


class WalletLedgerView(APIView):
    """GET /api/wallet/ledger/ — recent immutable entries."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 50)), 100)
        data = WalletService.list_ledger(request.user, limit=limit)
        return _ok("Ledger retrieved.", data)


class WalletIntentsView(APIView):
    """GET /api/wallet/intents/ — deposit/spend intent history."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 30)), 100)
        data = WalletService.list_intents(request.user, limit=limit)
        return _ok("Intents retrieved.", data)


class WalletDepositView(APIView):
    """
    POST /api/wallet/deposits/

    Creates a deposit intent (PENDING_PROVIDER). Does not credit balance.
    Next steps: initiate STK/Airtel using intent.amount, attach provider ref,
    then apply_provider_success on callback.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = DepositCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            intent = DepositService.create_deposit_intent(
                request.user,
                amount=d["amount"],
                channel=d["channel"],
                idempotency_key=d["idempotency_key"],
                description=d.get("description") or "",
            )
        except WalletError as exc:
            return _err(exc)

        return _ok(
            "Deposit intent created. Credit applies only after provider success.",
            {
                "intent_id": str(intent.id),
                "status": intent.status,
                "amount": str(intent.amount),
                "channel": intent.channel,
                "idempotency_key": intent.idempotency_key,
                "note": "Call provider STK/Airtel; on SUCCESS use DepositService.apply_provider_success",
            },
            code=status.HTTP_201_CREATED,
        )


class WalletSpendView(APIView):
    """
    POST /api/wallet/spend/

    Pay fare from wallet. Amount from FareQuote.discounted_fare (fare_bridge).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = SpendCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            data = SpendService.create_and_settle_spend(
                request.user,
                quote_id=d["quote_id"],
                idempotency_key=d["idempotency_key"],
                booking_id=d.get("booking_id"),
                description=d.get("description") or "",
            )
        except WalletError as exc:
            return _err(exc)
        return _ok("Wallet spend settled.", data)
