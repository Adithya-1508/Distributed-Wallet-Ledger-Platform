from sqlalchemy.orm import Session

from app.db.models.transaction import (
    Transaction,
    TransactionStatus,
    TransactionType,
)


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, type: TransactionType, currency: str) -> Transaction:
        txn = Transaction(
            type=type,
            status=TransactionStatus.PENDING,
            currency=currency,
        )
        self.db.add(txn)
        self.db.flush()  # assigns the id, stays inside the transaction
        self.db.refresh(txn)
        return txn

    def mark_completed(self, txn: Transaction) -> Transaction:
        txn.status = TransactionStatus.COMPLETED
        self.db.flush()
        return txn
