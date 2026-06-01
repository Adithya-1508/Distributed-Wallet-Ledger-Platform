"""Entrypoint: python -m app.events.run_consumer"""
import logging

from app.core.config import settings
from app.events.consumer import NotificationConsumer
from app.events.producer import build_consumer

if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    consumer = build_consumer(group_id="notification-consumer")
    NotificationConsumer(
        consumer, topic=settings.kafka_topic_transactions
    ).run_forever()
