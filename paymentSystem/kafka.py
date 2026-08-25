import json
import logging
import time

from decouple import config

logger = logging.getLogger(__name__)

PRODUCER_METRICS_TO_LOG = (
    'record-send-rate',
    'record-retry-rate',
    'record-error-rate',
    'request-latency-avg',
    'requests-in-flight',
    'record-queue-time-avg',
    'record-queue-time-max',
    'batch-size-avg',
    'batch-size-max',
    'byte-rate',
    'metadata-age',
)

CONSUMER_METRICS_TO_LOG = (
    'records-consumed-rate',
    'bytes-consumed-rate',
    'fetch-latency-avg',
    'fetch-latency-max',
    'fetch-rate',
    'fetch-size-avg',
    'fetch-size-max',
    'records-per-request-avg',
    'commit-latency-avg',
    'commit-latency-max',
    'commit-rate',
    'assigned-partitions',
    'connection-count',
)


def _config_optional(name, default=None, cast=None):
    value = config(name, default=default, cast=cast) if cast else config(name, default=default)
    return value if value not in ('', None) else None


def _config_int(name, default):
    return config(name, default=default, cast=int)


def _config_bool(name, default):
    return config(name, default=default, cast=bool)


def _kafka_settings():
    """
    Collect transport settings in one place so production tuning can move to
    Django settings or a dedicated config object without touching call sites.
    """
    brokers = config('KAFKA_BROKERS', default='localhost:9092')
    return {
        'brokers': [broker.strip() for broker in brokers.split(',') if broker.strip()],
        'topic': config('KAFKA_PAYMENT_EVENTS_TOPIC', default='payment-events'),
        'client_id': config('KAFKA_CLIENT_ID', default='ridehaiingbackend-payments'),
        'group_id': config('KAFKA_PAYMENT_GROUP_ID', default='payment-state-projector'),
        'group_instance_id': _config_optional('KAFKA_PAYMENT_GROUP_INSTANCE_ID'),
        'security_protocol': config('KAFKA_SECURITY_PROTOCOL', default='PLAINTEXT'),
        'sasl_mechanism': _config_optional('KAFKA_SASL_MECHANISM'),
        'sasl_plain_username': _config_optional('KAFKA_SASL_USERNAME'),
        'sasl_plain_password': _config_optional('KAFKA_SASL_PASSWORD'),
        'ssl_cafile': _config_optional('KAFKA_SSL_CAFILE'),
        'ssl_certfile': _config_optional('KAFKA_SSL_CERTFILE'),
        'ssl_keyfile': _config_optional('KAFKA_SSL_KEYFILE'),
    }


def _producer_settings():
    """
    Kafka's durable producer posture is a small set of cooperating settings:
    all replicas must ack, idempotence must be on, retries must be enabled, and
    in-flight requests must stay constrained so a retry cannot reorder events.
    """
    settings = {
        'acks': config('KAFKA_PRODUCER_ACKS', default='all'),
        'enable_idempotence': _config_bool('KAFKA_PRODUCER_ENABLE_IDEMPOTENCE', True),
        'retries': _config_int('KAFKA_PRODUCER_RETRIES', 2147483647),
        'max_in_flight_requests_per_connection': _config_int(
            'KAFKA_PRODUCER_MAX_IN_FLIGHT_REQUESTS',
            1,
        ),
        'delivery_timeout_ms': _config_int('KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS', 120000),
        'request_timeout_ms': _config_int('KAFKA_PRODUCER_REQUEST_TIMEOUT_MS', 30000),
        'retry_backoff_ms': _config_int('KAFKA_PRODUCER_RETRY_BACKOFF_MS', 100),
        'reconnect_backoff_ms': _config_int('KAFKA_PRODUCER_RECONNECT_BACKOFF_MS', 50),
        'reconnect_backoff_max_ms': _config_int('KAFKA_PRODUCER_RECONNECT_BACKOFF_MAX_MS', 30000),
        'linger_ms': _config_int('KAFKA_PRODUCER_LINGER_MS', 5),
        'batch_size': _config_int('KAFKA_PRODUCER_BATCH_SIZE', 32768),
        'max_request_size': _config_int('KAFKA_PRODUCER_MAX_REQUEST_SIZE', 1048576),
        'max_block_ms': _config_int('KAFKA_PRODUCER_MAX_BLOCK_MS', 60000),
        'compression_type': _compression_type(
            config('KAFKA_PRODUCER_COMPRESSION_TYPE', default='gzip')
        ),
        'connections_max_idle_ms': _config_int('KAFKA_PRODUCER_CONNECTIONS_MAX_IDLE_MS', 540000),
        'metadata_max_age_ms': _config_int('KAFKA_PRODUCER_METADATA_MAX_AGE_MS', 300000),
        'metrics_enabled': _config_bool('KAFKA_PRODUCER_METRICS_ENABLED', True),
        'metrics_sample_window_ms': _config_int('KAFKA_PRODUCER_METRICS_SAMPLE_WINDOW_MS', 30000),
        'metrics_num_samples': _config_int('KAFKA_PRODUCER_METRICS_NUM_SAMPLES', 2),
        'flush_timeout_s': config('KAFKA_PRODUCER_FLUSH_TIMEOUT_S', default=30.0, cast=float),
        'ack_timeout_s': config('KAFKA_PRODUCER_ACK_TIMEOUT_S', default=30.0, cast=float),
    }
    _validate_producer_settings(settings)
    return settings


def _consumer_settings(from_beginning=False):
    """
    Consumer robustness is mostly about bounded work and explicit ownership:
    fetch only what can be processed before max_poll_interval_ms, heartbeat
    often enough to keep the group stable, and commit only after the DB update.
    """
    settings = {
        'enable_auto_commit': _config_bool('KAFKA_CONSUMER_ENABLE_AUTO_COMMIT', False),
        'auto_offset_reset': (
            'earliest'
            if from_beginning
            else config('KAFKA_CONSUMER_AUTO_OFFSET_RESET', default='latest').strip().lower()
        ),
        'isolation_level': config(
            'KAFKA_CONSUMER_ISOLATION_LEVEL',
            default='read_committed',
        ).strip().lower(),
        'allow_auto_create_topics': _config_bool('KAFKA_CONSUMER_ALLOW_AUTO_CREATE_TOPICS', False),
        'check_crcs': _config_bool('KAFKA_CONSUMER_CHECK_CRCS', True),
        'max_poll_records': _config_int('KAFKA_CONSUMER_MAX_POLL_RECORDS', 100),
        'max_poll_interval_ms': _config_int('KAFKA_CONSUMER_MAX_POLL_INTERVAL_MS', 300000),
        'session_timeout_ms': _config_int('KAFKA_CONSUMER_SESSION_TIMEOUT_MS', 10000),
        'heartbeat_interval_ms': _config_int('KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS', 3000),
        'request_timeout_ms': _config_int('KAFKA_CONSUMER_REQUEST_TIMEOUT_MS', 305000),
        'fetch_min_bytes': _config_int('KAFKA_CONSUMER_FETCH_MIN_BYTES', 1),
        'fetch_max_wait_ms': _config_int('KAFKA_CONSUMER_FETCH_MAX_WAIT_MS', 500),
        'fetch_max_bytes': _config_int('KAFKA_CONSUMER_FETCH_MAX_BYTES', 52428800),
        'max_partition_fetch_bytes': _config_int(
            'KAFKA_CONSUMER_MAX_PARTITION_FETCH_BYTES',
            1048576,
        ),
        'retry_backoff_ms': _config_int('KAFKA_CONSUMER_RETRY_BACKOFF_MS', 100),
        'reconnect_backoff_ms': _config_int('KAFKA_CONSUMER_RECONNECT_BACKOFF_MS', 50),
        'reconnect_backoff_max_ms': _config_int('KAFKA_CONSUMER_RECONNECT_BACKOFF_MAX_MS', 30000),
        'connections_max_idle_ms': _config_int('KAFKA_CONSUMER_CONNECTIONS_MAX_IDLE_MS', 540000),
        'metadata_max_age_ms': _config_int('KAFKA_CONSUMER_METADATA_MAX_AGE_MS', 300000),
        'max_in_flight_requests_per_connection': _config_int(
            'KAFKA_CONSUMER_MAX_IN_FLIGHT_REQUESTS',
            5,
        ),
        'metrics_enabled': _config_bool('KAFKA_CONSUMER_METRICS_ENABLED', True),
        'metrics_sample_window_ms': _config_int('KAFKA_CONSUMER_METRICS_SAMPLE_WINDOW_MS', 30000),
        'metrics_num_samples': _config_int('KAFKA_CONSUMER_METRICS_NUM_SAMPLES', 2),
        'commit_timeout_ms': _config_int('KAFKA_CONSUMER_COMMIT_TIMEOUT_MS', 30000),
        'metrics_log_every': _config_int('KAFKA_CONSUMER_METRICS_LOG_EVERY', 100),
    }
    _validate_consumer_settings(settings)
    return settings


def _compression_type(value):
    value = (value or '').strip().lower()
    return None if value in ('', 'none', 'null') else value


def _validate_producer_settings(settings):
    if settings['acks'] != 'all':
        raise ValueError("KAFKA_PRODUCER_ACKS must be 'all' for durable payment events.")
    if settings['enable_idempotence'] and settings['retries'] == 0:
        raise ValueError('KAFKA_PRODUCER_RETRIES must be greater than 0 when idempotence is enabled.')
    if settings['enable_idempotence'] and settings['max_in_flight_requests_per_connection'] != 1:
        raise ValueError(
            'kafka-python requires KAFKA_PRODUCER_MAX_IN_FLIGHT_REQUESTS=1 '
            'when idempotence is enabled.'
        )
    if settings['delivery_timeout_ms'] < settings['request_timeout_ms'] + settings['linger_ms']:
        raise ValueError(
            'KAFKA_PRODUCER_DELIVERY_TIMEOUT_MS must be at least '
            'KAFKA_PRODUCER_REQUEST_TIMEOUT_MS + KAFKA_PRODUCER_LINGER_MS.'
        )


def _validate_consumer_settings(settings):
    if settings['auto_offset_reset'] not in ('earliest', 'latest', 'none'):
        raise ValueError("KAFKA_CONSUMER_AUTO_OFFSET_RESET must be 'earliest', 'latest', or 'none'.")
    if settings['isolation_level'] not in ('read_committed', 'read_uncommitted'):
        raise ValueError(
            "KAFKA_CONSUMER_ISOLATION_LEVEL must be 'read_committed' or 'read_uncommitted'."
        )
    if settings['enable_auto_commit']:
        raise ValueError(
            'KAFKA_CONSUMER_ENABLE_AUTO_COMMIT must stay false so offsets commit '
            'only after the payment projection is updated.'
        )
    if settings['heartbeat_interval_ms'] >= settings['session_timeout_ms']:
        raise ValueError(
            'KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS must be lower than '
            'KAFKA_CONSUMER_SESSION_TIMEOUT_MS.'
        )
    if settings['heartbeat_interval_ms'] > settings['session_timeout_ms'] / 3:
        raise ValueError(
            'KAFKA_CONSUMER_HEARTBEAT_INTERVAL_MS should be no more than one third '
            'of KAFKA_CONSUMER_SESSION_TIMEOUT_MS.'
        )
    if settings['request_timeout_ms'] <= settings['session_timeout_ms']:
        raise ValueError(
            'KAFKA_CONSUMER_REQUEST_TIMEOUT_MS must be greater than '
            'KAFKA_CONSUMER_SESSION_TIMEOUT_MS.'
        )
    if not (
        settings['fetch_max_wait_ms']
        < settings['request_timeout_ms']
        < settings['connections_max_idle_ms']
    ):
        raise ValueError(
            'Kafka requires KAFKA_CONSUMER_FETCH_MAX_WAIT_MS < '
            'KAFKA_CONSUMER_REQUEST_TIMEOUT_MS < KAFKA_CONSUMER_CONNECTIONS_MAX_IDLE_MS.'
        )
    if settings['max_poll_records'] < 1:
        raise ValueError('KAFKA_CONSUMER_MAX_POLL_RECORDS must be greater than zero.')


def _event_to_message(event):
    return {
        'eventId': str(event.event_id),
        'paymentId': event.payment_id,
        'eventType': event.event_type,
        'occurredAt': event.occurred_at.isoformat(),
        'source': event.source,
        'correlationId': event.correlation_id,
        'providerReference': event.provider_reference,
        'payload': event.payload,
    }


def _json_serializer(value):
    return json.dumps(value, default=str, separators=(',', ':')).encode('utf-8')


def _safe_producer_config(config_values):
    sensitive = {'sasl_plain_password', 'ssl_keyfile'}
    return {
        key: '***' if key in sensitive and value else value
        for key, value in config_values.items()
    }


def _selected_metrics(producer):
    metrics = producer.metrics() or {}
    selected = {}
    for group_values in metrics.values():
        for name, value in group_values.items():
            if name in PRODUCER_METRICS_TO_LOG:
                selected[name] = value
    return selected


def _selected_consumer_metrics(consumer):
    metrics = consumer.metrics() or {}
    selected = {}
    for group_values in metrics.values():
        for name, value in group_values.items():
            if name in CONSUMER_METRICS_TO_LOG:
                selected[name] = value
    return selected


class _PaymentConsumerRebalanceListener:
    def __init__(self, topic, group_id):
        self.topic = topic
        self.group_id = group_id

    def on_partitions_revoked(self, revoked):
        logger.warning(
            'payment Kafka partitions revoked topic=%s group_id=%s partitions=%s',
            self.topic,
            self.group_id,
            sorted(str(partition) for partition in revoked),
        )

    def on_partitions_assigned(self, assigned):
        logger.info(
            'payment Kafka partitions assigned topic=%s group_id=%s partitions=%s',
            self.topic,
            self.group_id,
            sorted(str(partition) for partition in assigned),
        )


def _security_config(settings):
    security_config = {
        'security_protocol': settings['security_protocol'],
        'sasl_mechanism': settings['sasl_mechanism'],
        'sasl_plain_username': settings['sasl_plain_username'],
        'sasl_plain_password': settings['sasl_plain_password'],
        'ssl_cafile': settings['ssl_cafile'],
        'ssl_certfile': settings['ssl_certfile'],
        'ssl_keyfile': settings['ssl_keyfile'],
    }
    return {
        key: value
        for key, value in security_config.items()
        if value is not None
    }


class PaymentKafkaProducer:
    """
    Payment event producer with production-minded defaults and observable send
    boundaries. The wrapper stays intentionally small so it can later be split
    into a shared producer factory, async publisher, or metrics adapter.
    """

    def __init__(self):
        try:
            from kafka import KafkaProducer
        except ImportError as exc:
            raise RuntimeError('Install kafka-python to publish payment events.') from exc

        settings = _kafka_settings()
        producer_settings = _producer_settings()
        self.topic = settings['topic']
        self.flush_timeout_s = producer_settings.pop('flush_timeout_s')
        self.ack_timeout_s = producer_settings.pop('ack_timeout_s')
        producer_config = {
            'bootstrap_servers': settings['brokers'],
            'client_id': settings['client_id'],
            'key_serializer': lambda value: str(value).encode('utf-8'),
            'value_serializer': _json_serializer,
            **producer_settings,
            **_security_config(settings),
        }

        logger.info(
            'initializing payment Kafka producer topic=%s config=%s',
            self.topic,
            _safe_producer_config(producer_config),
        )
        self.producer = KafkaProducer(**producer_config)
        logger.info(
            'payment Kafka producer ready topic=%s metrics=%s',
            self.topic,
            _selected_metrics(self.producer),
        )

    def publish(self, event):
        """
        Publish and wait for the broker acknowledgement before the outbox row is
        marked published. The database outbox remains the retry boundary.
        """
        message = _event_to_message(event)
        key = event.payment_id
        event_id = message['eventId']
        serialized_value_size = len(_json_serializer(message))
        send_started = time.monotonic()

        logger.info(
            'enqueue payment event to Kafka topic=%s key=%s event_id=%s event_type=%s bytes=%s',
            self.topic,
            key,
            event_id,
            event.event_type,
            serialized_value_size,
        )

        try:
            future = self.producer.send(self.topic, key=key, value=message)
        except Exception:
            logger.exception(
                'failed before Kafka accepted event into producer buffer topic=%s key=%s event_id=%s',
                self.topic,
                key,
                event_id,
            )
            raise

        future.add_callback(self._log_ack, key=key, event_id=event_id)
        future.add_errback(self._log_send_failure, key=key, event_id=event_id)

        logger.debug(
            'flushing payment Kafka producer topic=%s key=%s event_id=%s timeout_s=%s',
            self.topic,
            key,
            event_id,
            self.flush_timeout_s,
        )
        flush_started = time.monotonic()
        self.producer.flush(timeout=self.flush_timeout_s)
        logger.debug(
            'payment Kafka flush completed topic=%s key=%s event_id=%s elapsed_ms=%s',
            self.topic,
            key,
            event_id,
            round((time.monotonic() - flush_started) * 1000, 2),
        )

        metadata = future.get(timeout=self.ack_timeout_s)
        logger.info(
            'payment Kafka publish completed topic=%s partition=%s offset=%s key=%s event_id=%s elapsed_ms=%s metrics=%s',
            metadata.topic,
            metadata.partition,
            metadata.offset,
            key,
            event_id,
            round((time.monotonic() - send_started) * 1000, 2),
            _selected_metrics(self.producer),
        )
        return metadata

    def close(self):
        logger.info('closing payment Kafka producer topic=%s', self.topic)
        self.producer.flush(timeout=self.flush_timeout_s)
        self.producer.close(timeout=self.flush_timeout_s)
        logger.info('payment Kafka producer closed topic=%s', self.topic)

    def _log_ack(self, metadata, key, event_id):
        logger.info(
            'Kafka ack received topic=%s partition=%s offset=%s key=%s event_id=%s',
            metadata.topic,
            metadata.partition,
            metadata.offset,
            key,
            event_id,
        )

    def _log_send_failure(self, exc, key, event_id):
        logger.error(
            'Kafka send failed after producer buffering topic=%s key=%s event_id=%s',
            self.topic,
            key,
            event_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


class PaymentKafkaConsumer:
    """
    Payment event consumer with explicit group-health, fetch, and offset commit
    settings. Processing still lives outside this wrapper; this class owns only
    Kafka transport and the observability around each delivery boundary.
    """

    def __init__(self, from_beginning=False):
        try:
            from kafka import ConsumerRebalanceListener, KafkaConsumer
        except ImportError as exc:
            raise RuntimeError('Install kafka-python to consume payment events.') from exc

        settings = _kafka_settings()
        consumer_settings = _consumer_settings(from_beginning=from_beginning)
        self.topic = settings['topic']
        self.group_id = settings['group_id']
        self.commit_timeout_ms = consumer_settings.pop('commit_timeout_ms')
        self.metrics_log_every = consumer_settings.pop('metrics_log_every')
        self.messages_seen = 0
        consumer_config = {
            'bootstrap_servers': settings['brokers'],
            'client_id': settings['client_id'],
            'group_id': settings['group_id'],
            'group_instance_id': settings['group_instance_id'],
            'key_deserializer': lambda value: value.decode('utf-8') if value else None,
            'value_deserializer': lambda value: json.loads(value.decode('utf-8')),
            **consumer_settings,
            **_security_config(settings),
        }
        consumer_config = {
            key: value
            for key, value in consumer_config.items()
            if value is not None
        }

        logger.info(
            'initializing payment Kafka consumer topic=%s group_id=%s config=%s from_beginning=%s',
            self.topic,
            self.group_id,
            _safe_producer_config(consumer_config),
            from_beginning,
        )
        self.consumer = KafkaConsumer(**consumer_config)
        listener = type(
            'PaymentConsumerRebalanceListener',
            (_PaymentConsumerRebalanceListener, ConsumerRebalanceListener),
            {},
        )(self.topic, self.group_id)
        self.consumer.subscribe([self.topic], listener=listener)
        logger.info(
            'payment Kafka consumer ready topic=%s group_id=%s metrics=%s',
            self.topic,
            self.group_id,
            _selected_consumer_metrics(self.consumer),
        )

    def __iter__(self):
        """
        Yield Kafka records and log the fetch/deserialization boundary. The
        caller still decides when processing succeeded and when to commit.
        """
        while True:
            try:
                for message in self.consumer:
                    self.messages_seen += 1
                    event_id = self._message_value(message).get('eventId')
                    logger.info(
                        'payment Kafka message consumed topic=%s partition=%s offset=%s key=%s event_id=%s count=%s',
                        message.topic,
                        message.partition,
                        message.offset,
                        message.key,
                        event_id,
                        self.messages_seen,
                    )
                    if (
                        self.metrics_log_every
                        and self.messages_seen % self.metrics_log_every == 0
                    ):
                        logger.info(
                            'payment Kafka consumer metrics topic=%s group_id=%s metrics=%s',
                            self.topic,
                            self.group_id,
                            _selected_consumer_metrics(self.consumer),
                        )
                    yield message
                return
            except Exception:
                logger.exception(
                    'payment Kafka consumer failed while polling topic=%s group_id=%s',
                    self.topic,
                    self.group_id,
                )
                raise

    def commit(self):
        """
        Commit only after the caller finishes the database projection update.
        This keeps failures at-least-once: a crash before commit is replayed.
        """
        commit_started = time.monotonic()
        logger.info(
            'committing payment Kafka offsets topic=%s group_id=%s assignment=%s',
            self.topic,
            self.group_id,
            sorted(str(partition) for partition in self.consumer.assignment()),
        )
        try:
            self.consumer.commit(timeout_ms=self.commit_timeout_ms)
        except Exception:
            logger.exception(
                'payment Kafka offset commit failed topic=%s group_id=%s timeout_ms=%s',
                self.topic,
                self.group_id,
                self.commit_timeout_ms,
            )
            raise
        logger.info(
            'payment Kafka offset commit completed topic=%s group_id=%s elapsed_ms=%s metrics=%s',
            self.topic,
            self.group_id,
            round((time.monotonic() - commit_started) * 1000, 2),
            _selected_consumer_metrics(self.consumer),
        )

    def close(self):
        logger.info(
            'closing payment Kafka consumer topic=%s group_id=%s',
            self.topic,
            self.group_id,
        )
        self.consumer.close(autocommit=False, timeout_ms=self.commit_timeout_ms)
        logger.info('payment Kafka consumer closed topic=%s group_id=%s', self.topic, self.group_id)

    def _message_value(self, message):
        return message.value if isinstance(message.value, dict) else {}
