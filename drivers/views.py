from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from Loginandauthentication.models import CustomUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView


from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
  # your user model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ride_matching.models import Booking
from .models import Driver
from rest_framework.permissions import IsAuthenticated, AllowAny

from .serializers import PhoneTokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import redis, json

from django.conf import settings
from django.utils.decorators import method_decorator
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Driver, Bus

r = redis.Redis(host='localhost', port=6379, db=0)


class SetAvailabilityAPIView(APIView):
    permission_classes = [AllowAny]  # or IsAuthenticated if token is validated

    def post(self, request):
        # Expect driver_id sent from client
        driver_id = request.data.get("driver_id")
        if not driver_id:
            return Response({"success": False, "message": "Missing 'driver_id' field"}, status=400)

        available = request.data.get("available")
        if available is None:
            return Response({"success": False, "message": "Missing 'available' field"}, status=400)

        # Fetch driver by ID
        try:
            driver = Driver.objects.get(user__id=driver_id)
        except Driver.DoesNotExist:
            return Response({"success": False, "message": "Driver profile not found"}, status=400)

        # Update availability
        driver.is_available = bool(available)
        driver.save()

        # Update Redis
        try:
            bus = driver.bus
            route_name = bus.route.name

            redis_hash_key = f"route:{route_name}:buses"
            redis_zset_key = f"route:{route_name}:availability"

            details_json = r.hget(redis_hash_key, str(bus.id))
            if details_json:
                details = json.loads(details_json)
                details["is_available"] = driver.is_available
                r.hset(redis_hash_key, str(bus.id), json.dumps(details))

        except Bus.DoesNotExist:
            pass

        return Response({
            "success": True,
            "message": "Availability updated",
            "available": driver.is_available
        })

class StartTripAPIView(APIView):
        permission_classes = [IsAuthenticated]

        def post(self, request):
            driver_id = request.data.get("driver_id")

            if not driver_id:
                return Response({"status": "error", "message": "driver_id is required"}, status=400)

            try:
                driver = CustomUser.objects.get(user_id=driver_id)
            except CustomUser.DoesNotExist:
                return Response({"status": "error", "message": "Driver not found"}, status=404)

            # Mark driver as online
            driver.is_online = True
            driver.save()

            return Response({
                "status": "success",
                "message": "Trip started. Driver is now online."
            })

class EndTripAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        driver_id = request.data.get("driver_id")

        if not driver_id:
            return Response({"status": "error", "message": "driver_id is required"}, status=400)

        try:
            driver = CustomUser.objects.get(user_id=driver_id)
        except CustomUser.DoesNotExist:
            return Response({"status": "error", "message": "Driver not found"}, status=404)

        # Mark driver as offline
        driver.is_online = False
        driver.save()

        return Response({
            "status": "success",
            "message": "Trip ended. Driver is now offline."
        })



class SetDriverAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not hasattr(user, 'driver_profile'):
            return Response({"error": "Not a driver"}, status=status.HTTP_403_FORBIDDEN)

        driver = user.driver_profile
        driver.is_available = True  # Driver confirmed availability
        driver.save()

        return Response({
            "status": "success",
            "is_available": driver.is_available
        }, status=status.HTTP_200_OK)


class PhoneTokenObtainPairView(TokenObtainPairView):
    serializer_class = PhoneTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        print("REQUEST DATA:", request.data)
        return super().post(request, *args, **kwargs)

class DriverOnlineStatusView(APIView):
    permission_classes = [IsAuthenticated]  # ensures JWT token is valid

    def post(self, request):
        user = request.user

        # Make sure the user is a driver
        if not hasattr(user, "driver_profile"):
            return Response({"error": "Not a driver"}, status=status.HTTP_403_FORBIDDEN)

        driver = user.driver_profile
        driver.is_online = True  # mark driver as online
        driver.save()

        return Response({"status": "Driver is now online", "is_online": driver.is_online})

    def delete(self, request):
        """Optional: handle going offline"""
        user = request.user

        if not hasattr(user, "driver_profile"):
            return Response({"error": "Not a driver"}, status=status.HTTP_403_FORBIDDEN)

        driver = user.driver_profile
        driver.is_online = False  # mark driver as offline
        driver.save()

        return Response({"status": "Driver is now offline", "is_online": driver.is_online})


class DriverComeOnlineAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        try:
            driver = user.driver_profile
        except Driver.DoesNotExist:
            return Response({"success": False, "message": "Driver profile not found"}, status=400)

        lat = request.data.get("lat")
        lng = request.data.get("lng")
        booking_id = request.data.get("booking_id")

        if lat is None or lng is None:
            return Response({"success": False, "message": "Missing coordinates"}, status=400)

        # Save location in Redis
        driver_loc_key = f"driver:{driver.id}:location"
        r.hset(driver_loc_key, mapping={"lat": lat, "lng": lng})
        r.expire(driver_loc_key, 600)

        channel_layer = get_channel_layer()

        # Specific booking → notify assigned rider
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id)
                rider_id = booking.user_id

                async_to_sync(channel_layer.group_send)(
                    f"user_{rider_id}",
                    {
                        "type": "send_json",
                        "data": {
                            "type": "driver_location_update",
                            "driver_id": driver.id,
                            "booking_id": booking.id,
                            "lat": lat,
                            "lng": lng
                        }
                    }
                )
            except Booking.DoesNotExist:
                pass

        else:
            # Broadcast to route watchers
            try:
                bus = driver.bus
                route_name = bus.route.name

                async_to_sync(channel_layer.group_send)(
                    f"route_{route_name}_watchers",
                    {
                        "type": "send_json",
                        "data": {
                            "type": "driver_location_update",
                            "driver_id": driver.id,
                            "lat": lat,
                            "lng": lng,
                            "route": route_name
                        }
                    }
                )
            except Bus.DoesNotExist:
                pass

        return Response({"success": True, "message": "Driver location broadcasted"})


class CancelAvailabilityView(APIView):
    permission_classes = [AllowAny]  # ← removed authentication

    def post(self, request):
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"success": False, "message": "Missing 'user_id' field"}, status=400)

        try:
            user = CustomUser.objects.get(id=user_id)
            driver = user.driver_profile
        except (CustomUser.DoesNotExist, Driver.DoesNotExist):
            return Response({"success": False, "message": "Driver profile not found"}, status=400)

        # 1. Check if driver is currently available
        if not driver.is_available:
            return Response(
                {"success": False, "message": "You are not currently available."},
                status=400
            )

        # 2. Check if driver has pending/accepted/ongoing bookings
        active_booking_exists = Booking.objects.filter(
            driver=driver,
            status__in=["PENDING", "ACCEPTED", "ONGOING"]
        ).exists()

        if active_booking_exists:
            return Response(
                {"success": False, "message": "Cannot cancel: customers are already queued or onboard."},
                status=403
            )

        # 3. Allow cancellation
        driver.is_available = False
        driver.save()

        # Optional: Update Redis if you are using it
        try:
            bus = driver.bus
            route_name = bus.route.name
            redis_hash_key = f"route:{route_name}:buses"
            details_json = r.hget(redis_hash_key, str(bus.id))
            if details_json:
                details = json.loads(details_json)
                details["is_available"] = driver.is_available
                r.hset(redis_hash_key, str(bus.id), json.dumps(details))
        except Bus.DoesNotExist:
            pass

        return Response(
            {"success": True, "message": "Availability cancelled successfully.", "available": driver.is_available},
            status=200
        )