from psycopg2 import DatabaseError
from rest_framework.response import Response

from drivers.models import Bus
from ride_matching.exceptions import BusException

#STACK UNWINDING ERROR HANDLING
def get_driver_bus_details(route_name):
    try:
        # IN Later versions an algorithmic assigning needs to be done here.
        bus = Bus.objects.filter(route__name=route_name, driver__is_available=True)
        return {
            "driver_id": bus.driver.id,
            "bus_id": bus.id,
            "route_name": bus.route.name,
            "registration_no": bus.registration_no,
            "capacity": bus.capacity,
            "departure_time": getattr(bus, "departure_time", None),
            "status": bus.status,
            "seats_available": bus.capacity,
            "is_available": bus.driver.is_available
        }
    except Bus.DoesNotExist:
        raise BusException
    except AttributeError as e:
       raise BusException("AttributeError while interacting with DB")
    except DatabaseError as e:
        raise BusException
    except Exception as e:
        raise BusException


