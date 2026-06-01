import uuid

from sqlalchemy import select

from app.db.models.ledger_entry import EntryType, LedgerEntry


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


def _make_wallet(client, headers, currency="INR"):
    return client.post(
        "/api/v1/wallets", json={"currency": currency}, headers=headers
    ).json()["id"]


def _balance(client, headers, wallet_id):
    return client.get(
        f"/api/v1/wallets/{wallet_id}/balance", headers=headers
    ).json()["available_balance"]


def _funded_wallet(client, email, amount, currency="INR"):
    headers = _register_and_login(client, email)
    wallet_id = _make_wallet(client, headers, currency)
    if amount:
        client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": amount, "currency": currency},
            headers=headers,
        )
    return headers, wallet_id


def test_transfer_moves_funds(client):
    h_a, w_a = _funded_wallet(client, "ta@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "tb@example.com", 0)

    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 40000, "currency": "INR"},
        headers=h_a,
    )
    assert resp.status_code == 200
    assert resp.json()["available_balance"] == 60000
    assert resp.json()["status"] == "COMPLETED"

    assert _balance(client, h_a, w_a) == 60000
    assert _balance(client, h_b, w_b) == 40000


def test_transfer_creates_balanced_ledger(client, db):
    h_a, w_a = _funded_wallet(client, "tbal_a@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "tbal_b@example.com", 0)

    txn_id = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 30000, "currency": "INR"},
        headers=h_a,
    ).json()["transaction_id"]

    entries = db.scalars(
        select(LedgerEntry).where(
            LedgerEntry.transaction_id == uuid.UUID(txn_id)
        )
    ).all()
    assert len(entries) == 2
    credits = sum(e.amount for e in entries if e.entry_type == EntryType.CREDIT)
    debits = sum(e.amount for e in entries if e.entry_type == EntryType.DEBIT)
    assert credits == debits == 30000


def test_conservation_of_money(client):
    """Total money across both wallets is unchanged by a transfer."""
    h_a, w_a = _funded_wallet(client, "cons_a@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "cons_b@example.com", 20000)
    before = _balance(client, h_a, w_a) + _balance(client, h_b, w_b)

    client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 45000, "currency": "INR"},
        headers=h_a,
    )
    after = _balance(client, h_a, w_a) + _balance(client, h_b, w_b)
    assert before == after == 120000


def test_transfer_insufficient_funds(client):
    h_a, w_a = _funded_wallet(client, "insuf_a@example.com", 10000)
    h_b, w_b = _funded_wallet(client, "insuf_b@example.com", 0)

    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 50000, "currency": "INR"},
        headers=h_a,
    )
    assert resp.status_code == 422
    # nothing moved
    assert _balance(client, h_a, w_a) == 10000
    assert _balance(client, h_b, w_b) == 0


def test_transfer_rejects_self_transfer(client):
    h_a, w_a = _funded_wallet(client, "self@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_a, "amount": 1000, "currency": "INR"},
        headers=h_a,
    )
    assert resp.status_code == 422


def test_transfer_currency_mismatch(client):
    h_a, w_a = _funded_wallet(client, "cur_a@example.com", 100000, currency="INR")
    h_b, w_b = _funded_wallet(client, "cur_b@example.com", 0, currency="USD")

    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 10000, "currency": "INR"},
        headers=h_a,
    )
    assert resp.status_code == 409


def test_transfer_requires_auth(client):
    h_a, w_a = _funded_wallet(client, "noauth_a@example.com", 100000)
    _, w_b = _funded_wallet(client, "noauth_b@example.com", 0)

    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 10000, "currency": "INR"},
    )
    assert resp.status_code == 401


def test_cannot_transfer_from_another_users_wallet(client):
    h_a, w_a = _funded_wallet(client, "owner@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "attacker@example.com", 0)

    # attacker (h_b) tries to spend from owner's wallet (w_a)
    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 10000, "currency": "INR"},
        headers=h_b,
    )
    assert resp.status_code == 404
    assert _balance(client, h_a, w_a) == 100000  # untouched


def test_transfer_recipient_not_found(client):
    h_a, w_a = _funded_wallet(client, "norcpt@example.com", 100000)
    resp = client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={
            "recipient_wallet_id": str(uuid.uuid4()),
            "amount": 10000,
            "currency": "INR",
        },
        headers=h_a,
    )
    assert resp.status_code == 404


def test_transfer_is_idempotent(client):
    """Same Idempotency-Key replays the original result; money moves once."""
    h_a, w_a = _funded_wallet(client, "idem_a@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "idem_b@example.com", 0)
    headers = {**h_a, "Idempotency-Key": "transfer-abc-123"}
    body = {"recipient_wallet_id": w_b, "amount": 40000, "currency": "INR"}

    r1 = client.post(f"/api/v1/wallets/{w_a}/transfer", json=body, headers=headers)
    r2 = client.post(f"/api/v1/wallets/{w_a}/transfer", json=body, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    # same transaction returned both times
    assert r1.json()["transaction_id"] == r2.json()["transaction_id"]
    # debited exactly once
    assert _balance(client, h_a, w_a) == 60000
    assert _balance(client, h_b, w_b) == 40000
