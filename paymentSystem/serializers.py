from rest_framework import serializers


class STKPushSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    booking_id = serializers.IntegerField(required=False, allow_null=True)
    account_reference = serializers.CharField(max_length=12, required=False, default='NexaRide')
    transaction_desc = serializers.CharField(max_length=13, required=False, default='Ride Payment')


class B2CSerializer(serializers.Serializer):
    COMMAND_CHOICES = ['BusinessPayment', 'SalaryPayment', 'PromotionPayment']

    phone_number = serializers.CharField(max_length=15)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    command_id = serializers.ChoiceField(choices=COMMAND_CHOICES, default='BusinessPayment')
    remarks = serializers.CharField(max_length=100, required=False, default='Payment')
    occasion = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
