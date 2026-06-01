"""Outbox publisher worker.

Drains unpublished rows from the outbox and ships them to Kafka, then stamps
`published_at`. Delivery is at-least-once: if the process dies after a message
is sent but before the row is marked, it is re-sent on restart -- so consumers
must dedupe.

The `producer` is duck-typed (anything with `.produce(...)` and `.flush(...)`),
which lets tests inject a fake and exercise the logic without a broker.
"""
import json
import logging
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.outbox_repo import OutboxRepository

log = logging.getLogger(__name__)


class OutboxPublisher:
    def __init__(
        self,
        producer,
        *,
        topic: str | None = None,
        batch_size: int = 100,
        flush_timeout: float = 10.0,
    ) -> None:
        self.producer = producer
        self.topic = topic or settings.kafka_topic_transactions
        self.batch_size = batch_size
        self.flush_timeout = flush_timeout
        self._delivery_errors: list = []

    def _on_delivery(self, err, _msg) -> None:
        if err is not None:
            self._delivery_errors.append(err)

    def publish_batch(self, db) -> int:
        """Publish one batch of pending events using session `db`.

        produce -> flush (wait for broker acks) -> mark published. The caller
        owns the commit. Returns how many events were published.
        """
        repo = OutboxRepository(db)
        events = repo.fetch_unpublished(limit=self.batch_size)
        if not events:
            return 0

        self._delivery_errors = []
        for event in events:
            self.producer.produce(
                topic=self.topic,
                key=str(event.aggregate_id),  # same txn -> same partition (order)
                value=json.dumps(event.payload).encode("utf-8"),
                headers=[("event_type", event.event_type.encode("utf-8"))],
                on_delivery=self._on_delivery,
            )
        self.producer.flush(self.flush_timeout)

        if self._delivery_errors:
            # Mark nothing; the whole batch is retried on the next loop. Some may
            # have actually landed -> at-least-once -> consumer dedupes.
            raise RuntimeError(f"kafka delivery failed: {self._delivery_errors}")

        for event in events:
            repo.mark_published(event)
        return len(events)


def run_forever(
    producer,
    *,
    session_factory=SessionLocal,
    poll_interval: float = 1.0,
) -> None:  # pragma: no cover - long-running loop
    publisher = OutboxPublisher(producer)
    log.info("outbox publisher started; topic=%s", publisher.topic)
    while True:
        published = 0
        db = session_factory()
        try:
            published = publisher.publish_batch(db)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("publish batch failed; will retry")
        finally:
            db.close()
        if published == 0:
            time.sleep(poll_interval)
