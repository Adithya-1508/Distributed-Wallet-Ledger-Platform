from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.transaction_stat import TransactionStat


class TransactionStatRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def increment(self, *, currency: str, type: str, amount: int) -> TransactionStat:
        """Add one transaction of (currency, type) to the rollup, creating the
        row on first sight."""
        stat = self.db.get(TransactionStat, {"currency": currency, "type": type})
        if stat is None:
            stat = TransactionStat(
                currency=currency, type=type, count=0, total_amount=0
            )
            self.db.add(stat)
        stat.count += 1
        stat.total_amount += amount
        self.db.flush()
        return stat

    def get(self, currency: str, type: str) -> TransactionStat | None:
        return self.db.get(TransactionStat, {"currency": currency, "type": type})

    def all(self) -> list[TransactionStat]:
        return list(self.db.scalars(select(TransactionStat)))
