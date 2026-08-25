from rest_framework import serializers


class UpdateNameSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=50)
    second_name = serializers.CharField(max_length=50)
    mutation_id = serializers.CharField(max_length=64)
    base_version = serializers.IntegerField(required=False, allow_null=True)


class PhoneRequestSerializer(serializers.Serializer):
    new_phone_number = serializers.CharField(max_length=20)
    mutation_id = serializers.CharField(max_length=64)


class PhoneConfirmSerializer(serializers.Serializer):
    challenge_id = serializers.CharField(max_length=64)
    otp = serializers.CharField(max_length=12)
    mutation_id = serializers.CharField(max_length=64)
