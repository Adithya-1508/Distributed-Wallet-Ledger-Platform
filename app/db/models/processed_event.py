import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedEvent(Base):
    """Consumer-side dedupe log (the "inbox" pattern).

    A stateful consumer records each (consumer, transaction_id) it has applied.
    Because delivery is at-least-once, the same event can arrive twice; the
    composite PK makes re-applying it impossible, giving exactly-once *effect*
    on top of at-least-once delivery.
    """

    __tablename__ = "processed_events"

    consumer: Mapped[str] = mapped_column(String(50), primary_key=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
