from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ride_matching", "0003_add_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="base_fare",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="List price before promo. Never null.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="discounted_fare",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Pay this (after promo). Null until quote; equals base when no promo.",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="fare_quote_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text="Links to FareQuote.quote_id used for this booking.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="promo_code",
            field=models.CharField(blank=True, max_length=8, null=True),
        ),
        migrations.CreateModel(
            name="FareQuote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quote_id", models.UUIDField(db_index=True, unique=True)),
                ("route_name", models.CharField(max_length=100)),
                (
                    "base_fare",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="List price. Never null.",
                        max_digits=10,
                    ),
                ),
                (
                    "discounted_fare",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Payment amount (= base if no promo).",
                        max_digits=10,
                    ),
                ),
                ("promo_code", models.CharField(blank=True, max_length=8, null=True)),
                ("promo_applied", models.BooleanField(default=False)),
                ("promo_reject_reason", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN", "Open"),
                            ("CONSUMED", "Consumed"),
                            ("ABANDONED", "Abandoned"),
                            ("EXPIRED", "Expired"),
                        ],
                        db_index=True,
                        default="OPEN",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                (
                    "booking",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fare_quotes",
                        to="ride_matching.booking",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fare_quotes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user", "status"], name="ride_matchi_user_id_fare_idx"),
                    models.Index(fields=["status", "expires_at"], name="ride_matchi_status_exp_idx"),
                ],
            },
        ),
    ]
