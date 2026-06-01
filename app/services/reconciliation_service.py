import uuid
from dataclasses import dataclass, field

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models.ledger_entry import EntryType, LedgerEntry
from app.db.models.wallet import Wallet


@dataclass
class Discrepancy:
    wallet_id: uuid.UUID
    cached_balance: int  # what the wallet row says
    ledger_balance: int  # what the immutable ledger says it should be

    @property
    def diff(self) -> int:
        return self.cached_balance - self.ledger_balance


@dataclass
class ReconciliationReport:
    wallets_checked: int
    discrepancies: list[Discrepancy] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.discrepancies


class ReconciliationService:
    """Verifies the core money invariant for every wallet:

        wallet.available_balance == SUM(credits) - SUM(debits)   (from the ledger)

    The ledger is the immutable source of truth; the wallet balance is a cache.
    Any drift means a bug -- this is the safety net that catches it.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _ledger_balances(self) -> dict[uuid.UUID, int]:
        signed_amount = case(
            (LedgerEntry.entry_type == EntryType.CREDIT, LedgerEntry.amount),
            else_=-LedgerEntry.amount,
        )
        rows = self.db.execute(
            select(LedgerEntry.wallet_id, func.sum(signed_amount))
            .where(LedgerEntry.wallet_id.is_not(None))
            .group_by(LedgerEntry.wallet_id)
        ).all()
        return {wallet_id: int(balance) for wallet_id, balance in rows}

    def check(self) -> ReconciliationReport:
        ledger = self._ledger_balances()
        wallets = list(self.db.scalars(select(Wallet)))

        discrepancies: list[Discrepancy] = []
        for wallet in wallets:
            ledger_balance = ledger.get(wallet.id, 0)
            if wallet.available_balance != ledger_balance:
                discrepancies.append(
                    Discrepancy(
                        wallet_id=wallet.id,
                        cached_balance=wallet.available_balance,
                        ledger_balance=ledger_balance,
                    )
                )

        return ReconciliationReport(
            wallets_checked=len(wallets), discrepancies=discrepancies
        )
