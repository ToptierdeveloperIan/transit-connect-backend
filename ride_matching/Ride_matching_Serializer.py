from rest_framework import serializers
from .models import Route

class Ride_matching_serializer(serializers.ModelSerializer):

    class Meta:
        model = Route
        fields = ['name']