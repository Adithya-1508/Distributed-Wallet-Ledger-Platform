import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.processed_event_repo import ProcessedEventRepository
from app.repositories.stats_repo import TransactionStatRepository


class AnalyticsService:
    """Consumes transaction events and maintains the analytics rollup.

    Idempotent via the inbox pattern: each event is recorded in processed_events
    and the aggregate is updated in the SAME commit. A re-delivered event is
    detected (or rejected by the composite PK) and skipped, so aggregates are
    never double-counted.
    """

    CONSUMER_NAME = "analytics"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.processed = ProcessedEventRepository(db)
        self.stats = TransactionStatRepository(db)

    def handle_event(self, payload: dict) -> bool:
        """Apply one event to the rollup. True if applied, False if a duplicate."""
        txn_id = uuid.UUID(payload["transaction_id"])

        if self.processed.is_processed(self.CONSUMER_NAME, txn_id):
            return False

        self.processed.mark_processed(self.CONSUMER_NAME, txn_id)
        self.stats.increment(
            currency=payload["currency"],
            type=payload["type"],
            amount=int(payload["amount"]),
        )
        try:
            self.db.commit()
        except IntegrityError:
            # Lost a race to another consumer instance that already recorded
            # this transaction_id; treat as an already-handled duplicate.
            self.db.rollback()
            return False
        return True
