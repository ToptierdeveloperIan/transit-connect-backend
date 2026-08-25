import time

from django.core.management.base import BaseCommand

from paymentSystem.event_service import mark_outbox_failed, mark_outbox_published
from paymentSystem.kafka import PaymentKafkaProducer
from paymentSystem.models import PaymentOutbox, PaymentOutboxStatus


class Command(BaseCommand):
    help = 'Publish pending payment outbox events to Kafka.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Publish one batch and exit.')
        parser.add_argument('--interval', type=float, default=1.0, help='Seconds between batches.')
        parser.add_argument('--limit', type=int, default=100, help='Max outbox records per batch.')

    def handle(self, *args, **options):
        producer = PaymentKafkaProducer()

        while True:
            pending = PaymentOutbox.objects.select_related('event').filter(
                status=PaymentOutboxStatus.PENDING,
            ).order_by('created_at')[:options['limit']]

            count = 0
            for outbox_record in pending:
                try:
                    producer.publish(outbox_record.event)
                    mark_outbox_published(outbox_record)
                    count += 1
                    self.stdout.write(
                        f'published {outbox_record.event.event_type} for {outbox_record.event.payment_id}'
                    )
                except Exception as exc:
                    mark_outbox_failed(outbox_record, exc)
                    self.stderr.write(str(exc))

            if options['once']:
                self.stdout.write(f'published {count} payment event(s)')
                return

            time.sleep(options['interval'])