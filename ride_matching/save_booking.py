from .models import Booking

def save_booking(user_id, bus_id, route_id):
    booking = Booking.objects.create(
        user_id=user_id,
        bus_id=bus_id,
        route_id=route_id,
        status="confirmed"
    )
    return booking
