# Promo status machine: ACTIVE → REDEEMED, add RESERVED/EXPIRED, widen status field

from django.db import migrations, models


def forwards_status_values(apps, schema_editor):
    DiscountCode = apps.get_model("RedeemAndRefferalSys", "DiscountCode")
    # Legacy ACTIVE meant "coupled to user account" → REDEEMED
    DiscountCode.objects.filter(status="ACTIVE").update(status="REDEEMED")
    # Integer leftovers from broken TextChoices (if any)
    DiscountCode.objects.filter(status="1").update(status="CREATED")
    DiscountCode.objects.filter(status="2").update(status="REDEEMED")
    DiscountCode.objects.filter(status="3").update(status="RESERVED")
    DiscountCode.objects.filter(status="4").update(status="REVOKED")
    DiscountCode.objects.filter(status="5").update(status="USED")


def backwards_status_values(apps, schema_editor):
    DiscountCode = apps.get_model("RedeemAndRefferalSys", "DiscountCode")
    DiscountCode.objects.filter(status="REDEEMED").update(status="ACTIVE")
    DiscountCode.objects.filter(status="EXPIRED").update(status="REVOKED")
    DiscountCode.objects.filter(status="RESERVED").update(status="ACTIVE")


class Migration(migrations.Migration):

    dependencies = [
        ("RedeemAndRefferalSys", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discountcode",
            name="status",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("REDEEMED", "Redeemed"),
                    ("RESERVED", "Reserved"),
                    ("USED", "Used"),
                    ("EXPIRED", "Expired"),
                    ("REVOKED", "Revoked"),
                ],
                db_index=True,
                default="CREATED",
                max_length=16,
            ),
        ),
        migrations.RunPython(forwards_status_values, backwards_status_values),
    ]
