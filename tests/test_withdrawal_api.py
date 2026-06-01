import uuid

from sqlalchemy import select

from app.db.models.ledger_entry import EntryType, LedgerEntry
from app.services.ledger_service import SYSTEM_ACCOUNT_FUNDING


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


def _balance(client, headers, wallet_id):
    return client.get(
        f"/api/v1/wallets/{wallet_id}/balance", headers=headers
    ).json()["available_balance"]


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


def test_withdraw_decreases_balance(client):
    headers, wallet_id = _funded_wallet(client, "wd1@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 30000, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["available_balance"] == 70000
    assert resp.json()["status"] == "COMPLETED"
    assert _balance(client, headers, wallet_id) == 70000


def test_withdraw_creates_balanced_ledger(client, db):
    headers, wallet_id = _funded_wallet(client, "wd2@example.com", 100000)
    txn_id = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 40000, "currency": "INR"},
        headers=headers,
    ).json()["transaction_id"]

    entries = db.scalars(
        select(LedgerEntry).where(
            LedgerEntry.transaction_id == uuid.UUID(txn_id)
        )
    ).all()
    assert len(entries) == 2

    credits = sum(e.amount for e in entries if e.entry_type == EntryType.CREDIT)
    debits = sum(e.amount for e in entries if e.entry_type == EntryType.DEBIT)
    assert credits == debits == 40000

    # the wallet is debited; external funding is credited
    debit = next(e for e in entries if e.entry_type == EntryType.DEBIT)
    credit = next(e for e in entries if e.entry_type == EntryType.CREDIT)
    assert str(debit.wallet_id) == wallet_id
    assert credit.system_account == SYSTEM_ACCOUNT_FUNDING


def test_deposit_then_withdraw_nets_to_zero(client, db):
    """Deposit X then withdraw X -> balance 0, and the wallet ledger nets to 0."""
    headers, wallet_id = _funded_wallet(client, "wd_net@example.com", 0)
    client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 75000, "currency": "INR"},
        headers=headers,
    )
    client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 75000, "currency": "INR"},
        headers=headers,
    )
    assert _balance(client, headers, wallet_id) == 0

    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.wallet_id == uuid.UUID(wallet_id))
    ).all()
    credits = sum(e.amount for e in entries if e.entry_type == EntryType.CREDIT)
    debits = sum(e.amount for e in entries if e.entry_type == EntryType.DEBIT)
    assert credits - debits == 0


def test_withdraw_insufficient_funds(client):
    headers, wallet_id = _funded_wallet(client, "wd3@example.com", 10000)
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 50000, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert _balance(client, headers, wallet_id) == 10000  # unchanged


def test_withdraw_rejects_zero_amount(client):
    headers, wallet_id = _funded_wallet(client, "wd4@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 0, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_withdraw_rejects_wrong_currency(client):
    headers, wallet_id = _funded_wallet(client, "wd5@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 10000, "currency": "USD"},  # wallet is INR
        headers=headers,
    )
    assert resp.status_code == 409


def test_withdraw_requires_auth(client):
    _, wallet_id = _funded_wallet(client, "wd6@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/withdraw",
        json={"amount": 10000, "currency": "INR"},
    )
    assert resp.status_code == 401


def test_cannot_withdraw_from_another_users_wallet(client):
    h_a, w_a = _funded_wallet(client, "wd_owner@example.com", 100000)
    h_b, _ = _funded_wallet(client, "wd_attacker@example.com", 0)

    resp = client.post(
        f"/api/v1/wallets/{w_a}/withdraw",
        json={"amount": 10000, "currency": "INR"},
        headers=h_b,
    )
    assert resp.status_code == 404
    assert _balance(client, h_a, w_a) == 100000  # untouched


def test_withdraw_missing_wallet_returns_404(client):
    headers = _register_and_login(client, "wd7@example.com")
    resp = client.post(
        f"/api/v1/wallets/{uuid.uuid4()}/withdraw",
        json={"amount": 10000, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_withdraw_is_idempotent(client):
    """Same Idempotency-Key replays the original result; money leaves once."""
    headers, wallet_id = _funded_wallet(client, "wd_idem@example.com", 100000)
    h = {**headers, "Idempotency-Key": "withdraw-xyz-9"}
    body = {"amount": 40000, "currency": "INR"}

    r1 = client.post(f"/api/v1/wallets/{wallet_id}/withdraw", json=body, headers=h)
    r2 = client.post(f"/api/v1/wallets/{wallet_id}/withdraw", json=body, headers=h)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["transaction_id"] == r2.json()["transaction_id"]
    assert _balance(client, headers, wallet_id) == 60000  # debited once
