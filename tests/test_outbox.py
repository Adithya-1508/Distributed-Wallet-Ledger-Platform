import uuid

from sqlalchemy import select

from app.db.models.ledger_entry import LedgerEntry
from app.db.models.outbox import OutboxEvent
from app.repositories.outbox_repo import OutboxRepository


def _register_and_login(client, email):
    client.post(
        "/api/v1/users",
        json={"name": "T", "email": email, "password": "supersecret"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "supersecret"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _funded_wallet(client, email, amount, currency="INR"):
    headers = _register_and_login(client, email)
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": currency}, headers=headers
    ).json()["id"]
    if amount:
        client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": amount, "currency": currency},
            headers=headers,
        )
    return headers, wallet_id


def _events_for(db, txn_id):
    return db.scalars(
        select(OutboxEvent).where(OutboxEvent.aggregate_id == uuid.UUID(txn_id))
    ).all()


def test_deposit_writes_outbox_event(client, db):
    headers = _register_and_login(client, "ob_dep@example.com")
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=headers
    ).json()["id"]
    txn_id = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=headers,
    ).json()["transaction_id"]

    events = _events_for(db, txn_id)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "transaction.completed"
    assert event.aggregate_type == "transaction"
    assert event.published_at is None  # not yet sent
    assert event.payload["type"] == "DEPOSIT"
    assert event.payload["amount"] == 100000
    assert event.payload["wallet_id"] == wallet_id
    assert event.payload["status"] == "COMPLETED"


def test_transfer_writes_outbox_event_with_counterparty(client, db):
    h_a, w_a = _funded_wallet(client, "ob_ta@example.com", 100000)
    _, w_b = _funded_wallet(client, "ob_tb@example.com", 0)

    txn_id = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 30000, "currency": "INR"},
        headers=h_a,
    ).json()["transaction_id"]

    events = _events_for(db, txn_id)
    assert len(events) == 1
    payload = events[0].payload
    assert payload["type"] == "TRANSFER"
    assert payload["wallet_id"] == w_a
    assert payload["counterparty_wallet_id"] == w_b


def test_withdraw_writes_outbox_event(client, db):
    headers, wallet_id = _funded_wallet(client, "ob_wd@example.com", 100000)
    txn_id = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 40000, "currency": "INR"},
        headers=headers,
    ).json()["transaction_id"]

    events = _events_for(db, txn_id)
    assert len(events) == 1
    assert events[0].payload["type"] == "WITHDRAWAL"
    assert events[0].payload["counterparty_wallet_id"] is None


def test_failed_operation_writes_no_event(client, db):
    """Atomicity: an operation that doesn't commit leaves no outbox event
    (and no ledger entries) behind."""
    headers, wallet_id = _funded_wallet(client, "ob_fail@example.com", 10000)

    # withdraw more than the balance -> 422, nothing committed
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 999999, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 422

    # Only the funding deposit's event exists; the failed withdrawal added none.
    all_events = db.scalars(select(OutboxEvent)).all()
    assert all(e.payload["type"] == "DEPOSIT" for e in all_events)
    # ledger entries belong only to the deposit (2 legs), none from the failure
    all_legs = db.scalars(select(LedgerEntry)).all()
    assert {e.entry_type.value for e in all_legs} == {"CREDIT", "DEBIT"}


def test_outbox_event_count_matches_completed_transactions(client, db):
    """One event per committed money movement."""
    headers, wallet_id = _funded_wallet(client, "ob_count@example.com", 0)
    for amount in (10000, 20000, 30000):
        client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": amount, "currency": "INR"},
            headers=headers,
        )
    events = db.scalars(select(OutboxEvent)).all()
    assert len(events) == 3


def test_fetch_unpublished_and_mark_published(client, db):
    headers, wallet_id = _funded_wallet(client, "ob_pub@example.com", 0)
    client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 50000, "currency": "INR"},
        headers=headers,
    )

    repo = OutboxRepository(db)
    pending = repo.fetch_unpublished()
    assert len(pending) == 1

    repo.mark_published(pending[0])
    assert pending[0].published_at is not None
    assert repo.fetch_unpublished() == []  # nothing left to publish
