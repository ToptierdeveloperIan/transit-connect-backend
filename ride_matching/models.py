# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from Loginandauthentication.models import CustomUser
from drivers.models import Bus


class Route(models.Model):
    name = models.CharField(max_length=100)
    start_location_lat = models.FloatField()
    start_location_lng = models.FloatField()
    end_location_lat = models.FloatField()
    end_location_lng = models.FloatField()
    description = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    price =models.IntegerField()
    destinations_list = models.JSONField(default=list)  # e.g. ["CBD", "Cabanas", "Kitengela"]

    def __str__(self):
        return self.name


class Destination(models.Model):
    route = models.ForeignKey(Route, related_name="destinations", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    lat = models.FloatField()
    lng = models.FloatField()
    order = models.PositiveIntegerField(default=0)  # optional, for sequencing stops

    def __str__(self):
        return f"{self.name} ({self.route.name})"

class UserSelectedRoute(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'route')

class Booking(models.Model):
    """
    Ride booking row.

    Pricing (two fields only):
      - base_fare: always set (never null). List price / Route.price. Default 0 until quote.
      - discounted_fare: nullable. What payment charges when set (= base if no promo).
        amount_due is NOT a separate column — payment reads discounted_fare.

    See FareQuoteService and FARE_QUOTE.md.
    """

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="bookings")
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="bookings")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="bookings")
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("confirmed", "Confirmed"),
            ("active", "Cancelled"),
            ("completed", "Completed")
        ],
        default="cancelled"
    )

    # base_fare NEVER null — list price (0 until priced from route/quote)
    base_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="List price before promo. Never null.",
    )
    # discounted_fare = amount to pay; null until quote applied
    discounted_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Pay this (after promo). Null until quote; equals base when no promo.",
    )
    promo_code = models.CharField(max_length=8, null=True, blank=True)
    fare_quote_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Links to FareQuote.quote_id used for this booking.",
    )

    def __str__(self):
        return f"Booking {self.id} by {self.user.username} on bus {self.bus.registration_no}"


class FareQuote(models.Model):
    """
    Durable fare quote (two prices only):

      base_fare        — list price (never null)
      discounted_fare  — what payment charges (base if no promo)

    There is no separate amount_due column: amount_due == discounted_fare.

    Written when FareQuoteService runs inside get_route_coordinates on fare.
    Redis + DB for robustness; service monitors OPEN → abandon/expire.

    Status: OPEN | CONSUMED | ABANDONED | EXPIRED
    """

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CONSUMED = "CONSUMED", "Consumed"
        ABANDONED = "ABANDONED", "Abandoned"
        EXPIRED = "EXPIRED", "Expired"

    quote_id = models.UUIDField(unique=True, db_index=True)
    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fare_quotes",
    )
    route_name = models.CharField(max_length=100)
    base_fare = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="List price. Never null.",
    )
    discounted_fare = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Payment amount (= base if no promo).",
    )
    promo_code = models.CharField(max_length=8, null=True, blank=True)
    promo_applied = models.BooleanField(default=False)
    promo_reject_reason = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    booking = models.ForeignKey(
        Booking,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fare_quotes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"FareQuote {self.quote_id} {self.status} pay={self.discounted_fare}"

class DriverLocation(models.Model):
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE)
    lat = models.FloatField()
    lng = models.FloatField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Driver {self.driver.username} at ({self.lat}, {self.lng})"


class TripControl(models.Model):
    bus = models.OneToOneField(Bus, on_delete=models.CASCADE)
    threshold_percentage = models.FloatField(default=0.8)  # e.g., 80% booking
    cutoff_time = models.TimeField(null=True, blank=True)  # latest departure time if not full

    def __str__(self):
        return f"TripControl for Bus {self.bus.id}"


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification to {self.user.username}"

