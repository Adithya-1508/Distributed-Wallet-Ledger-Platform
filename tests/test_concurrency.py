"""Concurrency proof: SELECT ... FOR UPDATE prevents double-spend / lost updates.

The normal test harness pins one connection and fakes commits with savepoints,
so it CAN'T exercise real lock contention. These tests use their own engine with
a real connection pool and real commits, drive LedgerService from several
threads at once, and clean up the committed rows afterwards.
"""
import threading
import uuid

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.ledger_entry import LedgerEntry
from app.db.models.outbox import OutboxEvent
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.db.models.wallet import Wallet
from app.schemas.deposit import DepositRequest
from app.schemas.withdrawal import WithdrawalRequest
from app.services.ledger_service import InsufficientFundsError, LedgerService

# Real engine to the test DB: a connection pool + real commits, so the row lock
# actually contends across threads (unlike the savepoint-isolated `db` fixture).
_TEST_URL = make_url(settings.database_url).set(database="wallet_test")
_engine = create_engine(_TEST_URL, pool_size=10, max_overflow=5)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture
def real_wallet():
    """Create a committed user + INR wallet (balance 0); delete everything after."""
    user_id = uuid.uuid4()
    wallet_id = uuid.uuid4()
    s = _Session()
    try:
        s.add(User(id=user_id, name="C", email=f"conc-{user_id}@x.com", password_hash="x"))
        s.add(Wallet(id=wallet_id, user_id=user_id, currency="INR",
                     available_balance=0, locked_balance=0))
        s.commit()
    finally:
        s.close()

    yield user_id, wallet_id

    s = _Session()
    try:
        txn_ids = list(
            s.scalars(
                select(LedgerEntry.transaction_id).where(
                    LedgerEntry.wallet_id == wallet_id
                )
            )
        )
        if txn_ids:
            s.execute(delete(LedgerEntry).where(LedgerEntry.transaction_id.in_(txn_ids)))
            s.execute(delete(OutboxEvent).where(OutboxEvent.aggregate_id.in_(txn_ids)))
            s.execute(delete(Transaction).where(Transaction.id.in_(txn_ids)))
        s.execute(delete(Wallet).where(Wallet.id == wallet_id))
        s.execute(delete(User).where(User.id == user_id))
        s.commit()
    finally:
        s.close()


def _run_threads(target, n):
    barrier = threading.Barrier(n)
    threads = [threading.Thread(target=target, args=(barrier,)) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)


def _balance(wallet_id):
    s = _Session()
    try:
        return s.get(Wallet, wallet_id).available_balance
    finally:
        s.close()


def test_concurrent_withdrawals_no_double_spend(real_wallet):
    """Fund a wallet with exactly ONE withdrawal's worth, fire N at once:
    exactly one must succeed, the rest hit insufficient funds, balance never < 0."""
    user_id, wallet_id = real_wallet
    n = 8
    amount = 100

    # fund with exactly one withdrawal
    s = _Session()
    try:
        s.get(Wallet, wallet_id).available_balance = amount
        s.commit()
    finally:
        s.close()

    outcomes: list[str] = []
    lock = threading.Lock()

    def worker(barrier: threading.Barrier):
        barrier.wait()  # all threads pounce together to maximise contention
        session = _Session()
        try:
            LedgerService(session).withdraw(
                wallet_id=wallet_id,
                requester_id=user_id,
                data=WithdrawalRequest(amount=amount, currency="INR"),
            )
            result = "ok"
        except InsufficientFundsError:
            result = "insufficient"
        except Exception as exc:  # surfaces any unexpected race failure
            result = f"error:{type(exc).__name__}"
        finally:
            session.close()
        with lock:
            outcomes.append(result)

    _run_threads(worker, n)

    assert outcomes.count("ok") == 1, outcomes          # serialized: one winner
    assert outcomes.count("insufficient") == n - 1, outcomes
    assert _balance(wallet_id) == 0                      # never overdrawn


def test_concurrent_deposits_no_lost_update(real_wallet):
    """N concurrent deposits must all land: balance == N * amount (no lost
    increments, because each deposit holds the row lock while it adds)."""
    user_id, wallet_id = real_wallet
    n = 10
    amount = 500

    def worker(barrier: threading.Barrier):
        barrier.wait()
        session = _Session()
        try:
            LedgerService(session).deposit(
                wallet_id=wallet_id,
                requester_id=user_id,
                data=DepositRequest(amount=amount, currency="INR"),
            )
        finally:
            session.close()

    _run_threads(worker, n)

    assert _balance(wallet_id) == n * amount
