from django.core.management.base import BaseCommand

from paymentSystem.event_service import store_incoming_payment_event
from paymentSystem.kafka import PaymentKafkaConsumer


class Command(BaseCommand):
    help = 'Consume Kafka payment events and update the payment projection.'

    def add_arguments(self, parser):
        parser.add_argument('--from-beginning', action='store_true', help='Replay topic from earliest offset.')

    def handle(self, *args, **options):
        consumer = PaymentKafkaConsumer(from_beginning=options['from_beginning'])
        self.stdout.write('payment event consumer started')

        for message in consumer:
            applied, reason = store_incoming_payment_event(message.value)
            consumer.commit()
            self.stdout.write(
                f"{message.value['paymentId']} {message.value['eventType']} applied={applied} reason={reason}"
            )