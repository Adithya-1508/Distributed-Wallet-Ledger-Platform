import uuid

from sqlalchemy.orm import Session

from app.db.models.ledger_entry import EntryType
from app.db.models.transaction import Transaction, TransactionType
from app.db.models.wallet import Wallet
from app.repositories.ledger_repo import LedgerRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.wallet_repo import WalletRepository
from app.schemas.deposit import DepositRequest

# Reuse the wallet exceptions so the route maps them the same way everywhere.
from app.services.wallet_service import (
    WalletAccessDeniedError,
    WalletNotFoundError,
)

# Named system account that funds external deposits. Every deposit debits this
# account and credits the user wallet, so the two legs net to zero.
SYSTEM_ACCOUNT_FUNDING = "EXTERNAL_FUNDING"


class CurrencyMismatchError(Exception):
    """Deposit currency does not match the wallet's currency."""


class LedgerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletRepository(db)
        self.transactions = TransactionRepository(db)
        self.ledger = LedgerRepository(db)

    def deposit(
        self,
        *,
        wallet_id: uuid.UUID,
        requester_id: uuid.UUID,
        data: DepositRequest,
    ) -> tuple[Transaction, Wallet]:
        # 1. Lock the wallet row (SELECT ... FOR UPDATE). Concurrent writes to
        #    the same wallet serialise here until we commit.
        wallet = self.wallets.get_with_lock(wallet_id)
        if wallet is None:
            raise WalletNotFoundError(wallet_id)
        if wallet.user_id != requester_id:
            raise WalletAccessDeniedError(wallet_id)
        if wallet.currency != data.currency.upper():
            raise CurrencyMismatchError(
                f"Wallet currency {wallet.currency} != {data.currency.upper()}"
            )

        amount = data.amount

        # 2. Open the transaction (PENDING). If anything below fails, it never
        #    reaches COMPLETED and the whole unit of work rolls back.
        txn = self.transactions.create(
            type=TransactionType.DEPOSIT,
            currency=wallet.currency,
        )

        # 3. Two balanced ledger entries: money INTO the wallet, OUT OF the
        #    external funding account. credits == debits == amount.
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.CREDIT,
            amount=amount,
            currency=wallet.currency,
            wallet_id=wallet.id,
        )
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency=wallet.currency,
            system_account=SYSTEM_ACCOUNT_FUNDING,
        )

        # 4. Update the cached balance (safe: we hold the row lock).
        wallet.available_balance += amount

        # 5. Mark COMPLETED and commit everything atomically.
        self.transactions.mark_completed(txn)
        self.db.commit()

        # TODO(phase-3): idempotency-key check so a retried request is a no-op.
        # TODO(phase-5): publish a TransactionCompleted event via the outbox.

        self.db.refresh(wallet)
        self.db.refresh(txn)
        return txn, wallet
