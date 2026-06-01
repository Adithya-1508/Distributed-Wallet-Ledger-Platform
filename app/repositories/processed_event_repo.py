import uuid

from sqlalchemy.orm import Session

from app.db.models.processed_event import ProcessedEvent


class ProcessedEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def is_processed(self, consumer: str, transaction_id: uuid.UUID) -> bool:
        return (
            self.db.get(
                ProcessedEvent,
                {"consumer": consumer, "transaction_id": transaction_id},
            )
            is not None
        )

    def mark_processed(
        self, consumer: str, transaction_id: uuid.UUID
    ) -> ProcessedEvent:
        record = ProcessedEvent(consumer=consumer, transaction_id=transaction_id)
        self.db.add(record)
        self.db.flush()
        return record
