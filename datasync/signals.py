from django.db.models.signals import post_save
from django.dispatch import receiver

from Loginandauthentication.models import CustomUser
from ride_matching.models import Booking, Route

from .utils import bump_version


def safe_bump_version(resource_type, resource_id=None):
    try:
        bump_version(resource_type, resource_id)
    except Exception:
        pass


@receiver(post_save, sender=Route)
def route_saved(sender, instance, **kwargs):
    safe_bump_version("routes")


@receiver(post_save, sender=Booking)
def booking_saved(sender, instance, **kwargs):
    safe_bump_version("bookings", instance.user_id)


@receiver(post_save, sender=CustomUser)
def user_saved(sender, instance, **kwargs):
    safe_bump_version("profile", instance.pk)
