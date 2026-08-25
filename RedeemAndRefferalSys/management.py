from django.core.management.base import BaseCommand
from django.utils import timezone

from .models import DiscountCode
from .policy import should_revoke


class Command(BaseCommand):
    help = "Mark promo codes EXPIRED when shelf life or claim window has passed."

    def handle(self, *args, **options):
        now = timezone.now()

        # Time can kill codes that are not yet fully spent
        candidates = DiscountCode.objects.filter(
            status__in=[
                DiscountCode.Status.CREATED,
                DiscountCode.Status.REDEEMED,
                DiscountCode.Status.RESERVED,
            ]
        ).values_list("id", "expires_at", "status", "created_at", "redeemed_at")

        ids_to_expire = [
            obj_id
            for obj_id, expires_at, status, created_at, redeemed_at in candidates
            if should_revoke(
                expires_at,
                now,
                status,
                created_at=created_at,
                redeemed_at=redeemed_at,
            )
        ]

        if ids_to_expire:
            updated_count = DiscountCode.objects.filter(id__in=ids_to_expire).update(
                status=DiscountCode.Status.EXPIRED
            )
            self.stdout.write(
                self.style.SUCCESS(f"Marked {updated_count} promo codes EXPIRED.")
            )
        else:
            self.stdout.write(self.style.WARNING("No promo codes to expire."))
