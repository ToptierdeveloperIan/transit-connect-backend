from rest_framework import serializers

from drivers.models import Bus
from Loginandauthentication.models import CustomUser
from ride_matching.models import Booking, Destination, Route

from .models import ResourceVersion
from .utils import get_or_create_version


class ResourceVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceVersion
        fields = ("resource_type", "resource_id", "version", "updated_at")


class ProfileSyncSerializer(serializers.ModelSerializer):
    _version = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "phone_number",
            "first_name",
            "second_name",
            "profile_photo_url",
            "payment_methods",
            "rating",
            "current_location",
            "is_driver",
            "is_online",
            "created_at",
            "updated_at",
            "_version",
        )
        read_only_fields = (
            "id",
            "email",
            "phone_number",
            "rating",
            "is_driver",
            "created_at",
            "updated_at",
            "_version",
        )

    def get__version(self, obj):
        version = get_or_create_version("profile", obj.pk)
        return {"version": version.version, "updated_at": version.updated_at}


class DestinationSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = ("id", "name", "lat", "lng", "order")


class RouteSyncSerializer(serializers.ModelSerializer):
    destinations = DestinationSyncSerializer(many=True, read_only=True)
    _version = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = (
            "id",
            "name",
            "description",
            "start_location_lat",
            "start_location_lng",
            "end_location_lat",
            "end_location_lng",
            "destinations_list",
            "destinations",
            "updated_at",
            "_version",
        )
        read_only_fields = fields

    def get__version(self, obj):
        version = get_or_create_version("routes")
        return {"version": version.version, "updated_at": version.updated_at}


class BusSyncSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = Bus
        fields = ("id", "registration_no", "destination", "capacity", "status", "driver_name")

    def get_driver_name(self, obj):
        user = getattr(getattr(obj, "driver", None), "user", None)
        if not user:
            return None
        return f"{user.first_name} {user.second_name}".strip()


class BookingRouteSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = (
            "id",
            "name",
            "description",
            "start_location_lat",
            "start_location_lng",
            "end_location_lat",
            "end_location_lng",
        )


class BookingSyncSerializer(serializers.ModelSerializer):
    bus = BusSyncSerializer(read_only=True)
    route = BookingRouteSyncSerializer(read_only=True)
    _version = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ("id", "bus", "route", "timestamp", "status", "updated_at", "_version")
        read_only_fields = fields

    def get__version(self, obj):
        version = get_or_create_version("bookings", obj.user_id)
        return {"version": version.version, "updated_at": version.updated_at}
