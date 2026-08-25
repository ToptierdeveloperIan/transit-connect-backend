from ride_matching.exceptions import BusException
from ride_matching.assigning_algorithm import get_driver_bus_details
from ride_matching.models import Booking, Route
import redis, json, logging
from django.db import transaction
from ride_matching.utils import get_route_coordinates


r = redis.Redis(host='localhost', port=6379, db=0)  # your Redis config
logger = logging.getLogger(__name__)

def store_details_by_route(user_id, route_name, destination):
    try:
        # STEP 1 — Get driver + bus details
        details = get_driver_bus_details(route_name)

        # data obtained from details
        driver_id = details["driver_id"]
        bus_id = details["bus_id"]
        bus_route_name = details["route_name"]


        # STEP 3 — Bus route validation
        if bus_route_name.lower() != route_name.lower():
            raise BusException("Bus route name does not match")

        # STEP 4 — Bus availability check (seat or status) # note a bus cant be active if driver is available
        if details["seats_available"] <= 0:
            raise BusException("No seats available to proceed with booking")
        if details["status"] != "active":
            return {"error": "Bus is not active"}

        # STEP 5 — Route coordinates must exist
        coords = get_route_coordinates(route_name)

        # DEBUG HERE
        print("🔥 DEBUG: coords =", coords)
        print("🔥 DEBUG: coords type =", type(coords))
        if coords:
            print("🔥 DEBUG: coords keys =", coords.keys())
            print("🔥 DEBUG: destinations =", coords.get("destinations"))
            print("🔥 DEBUG: type(destinations) =", type(coords.get("destinations")))


        if not coords:
            return {"error": "Route coordinates not found"}

        destinations = coords.get("destinations") or []

        # STEP 5b — Ensure destination is valid for this route
        if destination.lower() not in [d.lower() for d in destinations]:
            return {"error": "Destination not valid for this route"}

        # STEP 6 — Save bus details + destination to Redis
        redis_hash_key = f"route:{route_name}:buses"
        redis_zset_key = f"route:{route_name}:availability"

        # include destination in the details
        details_with_dest = details.copy()
        details_with_dest["destination"] = destination

        r.hset(redis_hash_key, bus_id, json.dumps(details_with_dest))
        r.zadd(redis_zset_key, {bus_id: details["seats_available"]})
        r.expire(redis_hash_key, 3600)
        r.expire(redis_zset_key, 3600)

        # STEP 7 — Create booking in DB
        route_obj = Route.objects.get(name=route_name)
        with transaction.atomic():
            booking = Booking.objects.create(
                user_id=user_id,
                route=route_obj,
                bus_id=bus_id,

            )



        # SUCCESS RESPONSE TO FRONTEND
        return {
            "success": True,
            "message": "Booking created",
            "booking_id": booking.id,
            "coordinates": coords,
            "bus_details": details_with_dest
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {"error": "Unexpected error, try again later"}
