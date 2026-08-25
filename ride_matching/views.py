from winreg import error

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


from ride_matching.models import Route, Destination, Booking

from rest_framework.views import APIView
from drivers.store_details import store_details_by_route
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from ride_matching.utils import validate_route_and_stop


#def create_booking(request):
   # user_lat = request.data.get("lat")
   # user_lng = request.data.get("lng")

   # if is_inside_cbd(user_lat, user_lng):
       # return Response({"error": "Booking from inside CBD is not allowed"}, status=status.HTTP_400_BAD_REQUEST)

    # go on to book the driver depending on avialability


class CheckoutView(APIView):
    """
    POST /api/bookings/checkout/

    Light checkout path (NOT a canonical booking).

    Body: route_name, destination (stop), optional promo_code.
    Uses validate_route_and_stop + get_route_coordinates / FareQuoteService.
    Does NOT create Booking or call store_details_by_route.

    See CHECKOUT_API.md
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        route_name = request.data.get("route_name")
        destination = request.data.get("destination")
        promo_code = request.data.get("promo_code")

        result = validate_route_and_stop(
            route_name,
            destination,
            user=request.user,
            promo_code=promo_code,
            include_pricing=True,
        )

        if not result.get("success"):
            return Response(
                {
                    "success": False,
                    "error": result.get("error"),
                    "message": result.get("message"),
                    "allowed_stops": result.get("allowed_stops"),
                },
                status=400,
            )

        coordinates = result["coordinates"]
        quote_id = None
        if isinstance(coordinates, dict):
            quote_id = coordinates.get("quote_id")

        return Response(
            {
                "success": True,
                "message": "Checkout ready. Complete payment to confirm booking.",
                "route_name": result["route_name"],
                "stop": result["stop"],
                "destination": result["stop"],
                "coordinates": coordinates,
                "quote_id": quote_id,
                "booking_id": None,
            },
            status=200,
        )


class CreateBooking(APIView):
    """
    POST /api/bookings/create/ — legacy canonical match + Booking.create.
    Rider light path should use CheckoutView instead.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
            user = request.user
            print(request.data)
            # DATA IN JSON
            route_name = request.data.get("route_name")
            destination = request.data.get("destination")

            # 1. Simple validation
            if not route_name:
                return Response({"error": "Route name required"}, status=400)
            if not destination:
                return Response({"error": "Destination name required"}, status=400)

            # 2. Use helper method (single source of truth)
            result = store_details_by_route(user.id, route_name,destination)

            # 3. Helper returns error → bubble up
            if error in result:
                return Response({"error":error}, status=400)

            # 4. Success → return all driver/bus/coords
            return Response(result, status=200)

class CancelBookingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Find ACTIVE booking for this user
        try:
            booking = Booking.objects.get(user=user, status="confirmed")
        except Booking.DoesNotExist:
            return Response({"error": "No active booking found."}, status=404)

        # Prevent double cancellation
        if booking.status == "cancelled":
            return Response({"error": "Booking already cancelled."}, status=400)

        # Prevent cancelling completed trips
        if booking.status == "completed":
            return Response({"error": "Completed trips cannot be cancelled."}, status=400)

        # Refund seat count
        route = booking.route
        route.seats_available += 1
        route.save()

        booking.status = "cancelled"
        booking.save()

        return Response({
            "status": "Booking cancelled successfully.",
            "refunded_seat_to_route": route.route_name
        }, status=200)

class UpdateBookingStatus(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        status = request.data.get("status")

        if status not in ["confirmed", "cancelled", "completed"]:
            return Response({"success": False, "message": "Invalid status"}, status=400)

        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)
        except Booking.DoesNotExist:
            return Response({"success": False, "message": "Booking not found"}, status=404)

        # SEAT REFUND ON CANCEL
        if status == "cancelled" and booking.status != "cancelled":
            booking.bus.available_seats += 1
            booking.bus.save()

        booking.status = status
        booking.save()

        return Response({"success": True, "message": "Status updated"})

class GetActiveBooking(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        booking = Booking.objects.filter(
            user=request.user,
            status="confirmed"
        ).first()

        if not booking:
            return Response({"message": "No active booking"}, status=404)

        data = {
            "status": booking.status,
            "driver_name": booking.bus.driver.user.get_full_name(),
            "bus_plate": booking.bus.number_plate + " - " + booking.bus.model,
            "pickup": "Default",
            "destination": booking.route.end_location,
            "eta": str(12),  # keep as string for UI
            "payment_status": "Pending"
        }

        return Response(data)

