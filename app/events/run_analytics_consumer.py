"""Entrypoint: python -m app.events.run_analytics_consumer

A second consumer group on the same topic as the notification consumer. Kafka
fans the events out to both groups independently.
"""
import json
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.events.producer import build_consumer
from app.services.analytics_service import AnalyticsService

log = logging.getLogger(__name__)


def main() -> None:  # pragma: no cover - long-running loop
    consumer = build_consumer(group_id="analytics-consumer")
    consumer.subscribe([settings.kafka_topic_transactions])
    log.info("analytics consumer started; topic=%s", settings.kafka_topic_transactions)
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                log.error("consumer error: %s", msg.error())
                continue

            payload = json.loads(msg.value())
            db = SessionLocal()
            try:
                AnalyticsService(db).handle_event(payload)
            except Exception:
                log.exception("analytics handler failed")
            finally:
                db.close()
            consumer.commit(msg)  # at-least-once; handler is idempotent
    finally:
        consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
