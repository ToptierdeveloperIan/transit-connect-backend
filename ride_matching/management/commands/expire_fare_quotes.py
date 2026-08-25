"""
Management command: expire OPEN fare quotes past expires_at and clear Redis.

  python manage.py expire_fare_quotes

Schedule via cron (e.g. every 5 minutes) so abandoned checkouts free state.
"""

from django.core.management.base import BaseCommand

from ride_matching.services.fare_quote_service import FareQuoteService


class Command(BaseCommand):
    help = "Expire open fare quotes and clear Redis (payment quote monitor)."

    def handle(self, *args, **options):
        count = FareQuoteService().monitor_and_expire_open_quotes()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} fare quote(s)."))
