from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.transaction import (
    Transaction,
    TransactionStatus,
    TransactionType,
)


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        type: TransactionType,
        currency: str,
        idempotency_key: str | None = None,
    ) -> Transaction:
        txn = Transaction(
            type=type,
            status=TransactionStatus.PENDING,
            currency=currency,
            idempotency_key=idempotency_key,
        )
        self.db.add(txn)
        self.db.flush()  # assigns the id, stays inside the transaction
        self.db.refresh(txn)
        return txn

    def mark_completed(self, txn: Transaction) -> Transaction:
        txn.status = TransactionStatus.COMPLETED
        self.db.flush()
        return txn

    def get_by_idempotency_key(self, key: str) -> Transaction | None:
        return self.db.scalar(
            select(Transaction).where(Transaction.idempotency_key == key)
        )
