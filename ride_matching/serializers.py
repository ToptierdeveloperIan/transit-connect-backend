from rest_framework import serializers
from .models import Route, Destination, UserSelectedRoute


class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ('id', 'name', 'lat', 'lng', 'order')

class RouteSerializer(serializers.ModelSerializer):
    destinations = DestinationSerializer(many=True, read_only=True)

    class Meta:
        model = Route
        fields = ('id', 'name', 'description', 'start_point_lat', 'start_point_lng',
                  'end_point_lat', 'end_point_lng', 'destinations')

class UserSelectedRouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSelectedRoute
        fields = ('route', 'destination')
