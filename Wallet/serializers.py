from rest_framework import serializers

from Wallet.models import ProviderChannel


class DepositCreateSerializer(serializers.Serializer):
    """User requests a top-up; ledger credit happens only after provider success."""

    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    channel = serializers.ChoiceField(
        choices=[ProviderChannel.MPESA, ProviderChannel.AIRTEL]
    )
    idempotency_key = serializers.CharField(max_length=64)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class SpendCreateSerializer(serializers.Serializer):
    """
    Pay with wallet. Amount is NOT accepted from the client —
    server loads FareQuote.discounted_fare via fare_bridge.
    """

    quote_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=64)
    booking_id = serializers.IntegerField(required=False, allow_null=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
