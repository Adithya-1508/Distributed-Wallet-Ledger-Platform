"""Notification consumer.

Reads transaction events off Kafka and "notifies" (here: logs). Because the
publisher is at-least-once, the same event can arrive more than once, so we
dedupe on `transaction_id` before handling -- consumer-side idempotency.

The `consumer` is duck-typed so the dedupe/handle logic can be unit-tested
without a broker.
"""
import json
import logging

log = logging.getLogger(__name__)


class NotificationConsumer:
    def __init__(
        self,
        consumer,
        *,
        topic: str,
        handler=None,
        dedupe_store: set | None = None,
    ) -> None:
        self.consumer = consumer
        self.topic = topic
        self.handler = handler or self._default_handler
        # In-memory dedupe is fine for the demo. Production would persist this
        # (DB table / Redis) keyed by (consumer_group, transaction_id) so it
        # survives restarts.
        self.seen: set[str] = dedupe_store if dedupe_store is not None else set()

    def handle_event(self, payload: dict) -> bool:
        """Process one event idempotently. True if handled, False if a dup."""
        txn_id = payload.get("transaction_id")
        if txn_id in self.seen:
            log.info("duplicate event %s skipped", txn_id)
            return False
        self.handler(payload)
        self.seen.add(txn_id)
        return True

    def _default_handler(self, payload: dict) -> None:
        log.info(
            "NOTIFY: %s %s of %s minor units (%s) on wallet %s",
            payload.get("type"),
            payload.get("status"),
            payload.get("amount"),
            payload.get("currency"),
            payload.get("wallet_id"),
        )

    def run_forever(self) -> None:  # pragma: no cover - long-running loop
        self.consumer.subscribe([self.topic])
        log.info("notification consumer started; topic=%s", self.topic)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.error("consumer error: %s", msg.error())
                    continue
                payload = json.loads(msg.value())
                self.handle_event(payload)
                # Commit offset only after handling -> at-least-once.
                self.consumer.commit(msg)
        finally:
            self.consumer.close()
