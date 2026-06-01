import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ledger_entry import EntryType, LedgerEntry


class LedgerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_entry(
        self,
        *,
        transaction_id: uuid.UUID,
        entry_type: EntryType,
        amount: int,
        currency: str,
        wallet_id: uuid.UUID | None = None,
        system_account: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            transaction_id=transaction_id,
            entry_type=entry_type,
            amount=amount,
            currency=currency,
            wallet_id=wallet_id,
            system_account=system_account,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def get_entries_for_transaction(
        self, transaction_id: uuid.UUID
    ) -> list[LedgerEntry]:
        return list(
            self.db.scalars(
                select(LedgerEntry).where(
                    LedgerEntry.transaction_id == transaction_id
                )
            )
        )

    def get_entries_for_wallet(
        self, wallet_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> list[LedgerEntry]:
        """Newest-first ledger legs touching this wallet (paginated). Ordered by
        the monotonic `seq` so entries created in the same transaction (identical
        created_at) still sort deterministically by insertion order."""
        return list(
            self.db.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.wallet_id == wallet_id)
                .order_by(LedgerEntry.seq.desc())
                .limit(limit)
                .offset(offset)
            )
        )
