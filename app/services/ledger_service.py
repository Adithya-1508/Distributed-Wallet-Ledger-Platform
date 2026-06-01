import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.ledger_entry import EntryType
from app.db.models.transaction import Transaction, TransactionType
from app.db.models.wallet import Wallet
from app.repositories.ledger_repo import LedgerRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.wallet_repo import WalletRepository
from app.schemas.deposit import DepositRequest
from app.schemas.transfer import TransferRequest
from app.schemas.withdrawal import WithdrawalRequest

# Reuse the wallet exceptions so the route maps them the same way everywhere.
from app.services.wallet_service import (
    WalletAccessDeniedError,
    WalletNotFoundError,
)

# Named system account that funds external deposits. Every deposit debits this
# account and credits the user wallet, so the two legs net to zero.
SYSTEM_ACCOUNT_FUNDING = "EXTERNAL_FUNDING"


class CurrencyMismatchError(Exception):
    """Currency of the request/wallets does not line up."""


class InsufficientFundsError(Exception):
    """Sender wallet does not have enough available balance."""


class SameWalletTransferError(Exception):
    """Source and destination wallet are the same."""


class RecipientNotFoundError(Exception):
    """Destination wallet does not exist."""


class LedgerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletRepository(db)
        self.transactions = TransactionRepository(db)
        self.ledger = LedgerRepository(db)
        self.outbox = OutboxRepository(db)

    def _record_event(
        self,
        txn: Transaction,
        *,
        amount: int,
        wallet_id: uuid.UUID,
        counterparty_wallet_id: uuid.UUID | None = None,
    ) -> None:
        """Write the domain event into the outbox in the SAME transaction as the
        ledger. Either both commit or neither -- so no event is ever emitted for
        a transaction that rolled back, and any committed transaction always has
        its event sitting ready to publish. Solves the dual-write problem.
        """
        self.outbox.add_event(
            aggregate_type="transaction",
            aggregate_id=txn.id,
            event_type="transaction.completed",
            payload={
                "transaction_id": str(txn.id),
                "type": txn.type.value,
                "status": txn.status.value,
                "currency": txn.currency,
                "amount": amount,
                "wallet_id": str(wallet_id),
                "counterparty_wallet_id": (
                    str(counterparty_wallet_id)
                    if counterparty_wallet_id is not None
                    else None
                ),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            },
        )

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

        # 5. Mark COMPLETED, record the outbox event, commit atomically.
        self.transactions.mark_completed(txn)
        self._record_event(txn, amount=amount, wallet_id=wallet.id)
        self.db.commit()

        # Event is now in the outbox; a publisher worker drains it to Kafka
        # (phase-5b). The write above is atomic with the ledger.

        self.db.refresh(wallet)
        self.db.refresh(txn)
        return txn, wallet

    def transfer(
        self,
        *,
        sender_wallet_id: uuid.UUID,
        requester_id: uuid.UUID,
        data: TransferRequest,
        idempotency_key: str | None = None,
    ) -> tuple[Transaction, Wallet]:
        """Move money between two wallets. Returns (transaction, sender_wallet)."""
        recipient_wallet_id = data.recipient_wallet_id

        if sender_wallet_id == recipient_wallet_id:
            raise SameWalletTransferError(sender_wallet_id)

        # 0. Idempotency replay: if we've already processed this key, return the
        #    original transaction instead of moving money a second time.
        if idempotency_key:
            existing = self.transactions.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, self.wallets.get_by_id(sender_wallet_id)

        # 1. Lock BOTH wallet rows in a deadlock-safe (ascending id) order.
        locked = self.wallets.get_for_update_ordered(
            [sender_wallet_id, recipient_wallet_id]
        )
        sender = locked[sender_wallet_id]
        recipient = locked[recipient_wallet_id]

        # 2. Authorize + validate before any money moves.
        if sender is None:
            raise WalletNotFoundError(sender_wallet_id)
        if sender.user_id != requester_id:
            raise WalletAccessDeniedError(sender_wallet_id)
        if recipient is None:
            raise RecipientNotFoundError(recipient_wallet_id)
        if sender.currency != data.currency.upper():
            raise CurrencyMismatchError(
                f"Sender wallet currency {sender.currency} != {data.currency.upper()}"
            )
        if recipient.currency != sender.currency:
            raise CurrencyMismatchError(
                f"Recipient wallet currency {recipient.currency} != {sender.currency}"
            )

        amount = data.amount
        if sender.available_balance < amount:
            raise InsufficientFundsError(sender_wallet_id)

        # 3. Open the transfer transaction (carries the idempotency key).
        txn = self.transactions.create(
            type=TransactionType.TRANSFER,
            currency=sender.currency,
            idempotency_key=idempotency_key,
        )

        # 4. Two balanced ledger entries: out of sender, into recipient.
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency=sender.currency,
            wallet_id=sender.id,
        )
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.CREDIT,
            amount=amount,
            currency=sender.currency,
            wallet_id=recipient.id,
        )

        # 5. Update both cached balances (safe: we hold both row locks).
        sender.available_balance -= amount
        recipient.available_balance += amount

        # 6. Mark COMPLETED, record the outbox event, commit atomically.
        self.transactions.mark_completed(txn)
        self._record_event(
            txn,
            amount=amount,
            wallet_id=sender.id,
            counterparty_wallet_id=recipient.id,
        )
        try:
            self.db.commit()
        except IntegrityError:
            # A concurrent request with the same idempotency key won the race
            # (unique constraint). Roll back ours and return the winner's txn.
            self.db.rollback()
            if idempotency_key:
                existing = self.transactions.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing, self.wallets.get_by_id(sender_wallet_id)
            raise

        # Event is now in the outbox; a publisher worker drains it to Kafka
        # (phase-5b). The write above is atomic with the ledger.

        self.db.refresh(sender)
        self.db.refresh(txn)
        return txn, sender

    def withdraw(
        self,
        *,
        wallet_id: uuid.UUID,
        requester_id: uuid.UUID,
        data: WithdrawalRequest,
        idempotency_key: str | None = None,
    ) -> tuple[Transaction, Wallet]:
        """Take money out of a wallet to the external world.

        Mirror of deposit: DEBIT the wallet, CREDIT EXTERNAL_FUNDING. Guarded by
        an available-balance check (and the DB CHECK as a backstop).
        """
        # 0. Idempotency replay.
        if idempotency_key:
            existing = self.transactions.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, self.wallets.get_by_id(wallet_id)

        # 1. Lock the wallet row.
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
        if wallet.available_balance < amount:
            raise InsufficientFundsError(wallet_id)

        # 2. Open the transaction (carries the idempotency key).
        txn = self.transactions.create(
            type=TransactionType.WITHDRAWAL,
            currency=wallet.currency,
            idempotency_key=idempotency_key,
        )

        # 3. Two balanced entries: out of the wallet, back to external funding.
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.DEBIT,
            amount=amount,
            currency=wallet.currency,
            wallet_id=wallet.id,
        )
        self.ledger.create_entry(
            transaction_id=txn.id,
            entry_type=EntryType.CREDIT,
            amount=amount,
            currency=wallet.currency,
            system_account=SYSTEM_ACCOUNT_FUNDING,
        )

        # 4. Update the cached balance (safe: we hold the row lock).
        wallet.available_balance -= amount

        # 5. Mark COMPLETED, record the outbox event, commit atomically.
        self.transactions.mark_completed(txn)
        self._record_event(txn, amount=amount, wallet_id=wallet.id)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if idempotency_key:
                existing = self.transactions.get_by_idempotency_key(idempotency_key)
                if existing is not None:
                    return existing, self.wallets.get_by_id(wallet_id)
            raise

        # Event is now in the outbox; a publisher worker drains it to Kafka
        # (phase-5b). The write above is atomic with the ledger.

        self.db.refresh(wallet)
        self.db.refresh(txn)
        return txn, wallet
