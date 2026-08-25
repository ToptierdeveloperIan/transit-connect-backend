from django.db import transaction
from django.utils import timezone

from RedeemAndRefferalSys.models import DiscountCode
from RedeemAndRefferalSys.policy import is_time_valid, mark_expired


def validate_reserve_discount(discount: DiscountCode):
    """
    Hold a redeemed promo for checkout.

    REDEEMED → RESERVED (does not consume attempts).
    Payment success later → USED via consume_discount.
    """
    if discount.allowed_attempts <= 0:
        raise ValueError("Discount cannot be reserved: no attempts remaining")

    if discount.status != DiscountCode.Status.REDEEMED:
        raise ValueError("Discount must be REDEEMED (coupled to user) to reserve")

    if not is_time_valid(discount):
        mark_expired(discount)
        raise ValueError("Discount has expired (shelf life or claim window)")

    with transaction.atomic():
        locked_discount = DiscountCode.objects.select_for_update().get(pk=discount.pk)

        if locked_discount.allowed_attempts <= 0:
            raise ValueError("Discount cannot be reserved: no attempts remaining")

        if locked_discount.status != DiscountCode.Status.REDEEMED:
            raise ValueError("Discount must be REDEEMED to reserve")

        if not is_time_valid(locked_discount):
            mark_expired(locked_discount)
            raise ValueError("Discount has expired (shelf life or claim window)")

        locked_discount.status = DiscountCode.Status.RESERVED
        locked_discount.save(update_fields=["status"])
        return locked_discount


def consume_discount(discount: DiscountCode):
    """
    After canonical payment success only.

    RESERVED → USED (or REDEEMED if multi-use attempts remain).
    Decrements allowed_attempts on this code only.
    Does NOT overwrite redeemed_at (that is account-couple time).
    """
    with transaction.atomic():
        locked_discount = DiscountCode.objects.select_for_update().get(pk=discount.pk)

        if locked_discount.allowed_attempts <= 0:
            raise ValueError("Discount cannot be consumed: no attempts remaining")

        if locked_discount.status != DiscountCode.Status.RESERVED:
            raise ValueError("Discount must be RESERVED before consumption")

        locked_discount.allowed_attempts -= 1

        if locked_discount.allowed_attempts <= 0:
            locked_discount.allowed_attempts = 0
            locked_discount.status = DiscountCode.Status.USED
        else:
            # Multi-use: return to account-coupled state for another checkout
            locked_discount.status = DiscountCode.Status.REDEEMED

        locked_discount.save(update_fields=["allowed_attempts", "status"])
        return locked_discount


def calculate_fare(checkout):
    route = checkout.route
    route.refresh_from_db(fields=["price"])

    base_fare = getattr(route, "fare", route.price)
    discount_percentage = 0

    if checkout.promo_code:
        discount = DiscountCode.objects.get(code=checkout.promo_code)
        discount_percentage = getattr(
            discount,
            "discount_percentage",
            getattr(discount, "value", discount.Value_of_code),
        )

    discount_amount = base_fare * (discount_percentage / 100)
    fare_discounted = base_fare - discount_amount

    return {
        "base_fare": base_fare,
        "fare_discounted": max(fare_discounted, 0),
    }
