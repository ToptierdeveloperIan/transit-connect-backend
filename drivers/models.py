from django.db import models
from Loginandauthentication.models import CustomUser


class Driver(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="driver_profile")
    license_number = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=20, unique=True)
    is_available = models.BooleanField(default=False)
    datetime = models.DateTimeField(auto_now_add=True)
    rating_score = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    total_trips = models.IntegerField(default=0)
    last_rating = models.IntegerField(default=0)

    def __str__(self):
        return f"Driver {self.user.first_name} {self.user.second_name}"

class Bus(models.Model):
    registration_no = models.CharField(max_length=20, unique=True)
    driver = models.OneToOneField(Driver, on_delete=models.CASCADE, related_name="bus")
    route = models.ForeignKey("ride_matching.Route", on_delete=models.CASCADE)
    destination = models.CharField(max_length=255)
    capacity = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("waiting", "Waiting"),
            ("almost_full", "Almost Full"),
            ("departing", "Departing"),
            ("inbound", "Inbound"),
            ("arrived", "Arrived")
        ],
        default="waiting"
    )


