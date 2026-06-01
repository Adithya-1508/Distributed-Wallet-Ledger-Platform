"""confluent-kafka factory helpers.

Kept separate from the publisher/consumer logic so that logic stays
library-agnostic (duck-typed) and unit-testable without a broker.
"""
from confluent_kafka import Consumer, Producer

from app.core.config import settings


def build_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            # idempotent producer + acks=all => no duplicate/lost messages from
            # the producer's own retries.
            "enable.idempotence": True,
            "acks": "all",
        }
    )


def build_consumer(group_id: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            # We commit offsets manually AFTER handling, so a crash re-delivers
            # rather than silently dropping (at-least-once).
            "enable.auto.commit": False,
        }
    )
