import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.outbox import OutboxEvent


class OutboxRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        event_type: str,
        payload: dict,
    ) -> OutboxEvent:
        """Append an event. Flush only -- it joins the caller's transaction so it
        commits atomically with whatever ledger writes are in flight."""
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def fetch_unpublished(self, limit: int = 100) -> list[OutboxEvent]:
        """Oldest-first batch of events still waiting to be published."""
        return list(
            self.db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(limit)
            )
        )

    def mark_published(self, event: OutboxEvent) -> OutboxEvent:
        event.published_at = datetime.now(timezone.utc)
        self.db.flush()
        return event
