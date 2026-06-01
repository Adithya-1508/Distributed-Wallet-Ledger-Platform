import uuid

from sqlalchemy import select

from app.db.models.ledger_entry import EntryType, LedgerEntry


def _make_user_and_wallet(client, email, currency="INR"):
    client.post(
        "/api/v1/users",
        json={"name": "T", "email": email, "password": "supersecret"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "supersecret"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": currency}, headers=headers
    ).json()["id"]
    return headers, wallet_id


def test_deposit_increases_balance(client):
    headers, wallet_id = _make_user_and_wallet(client, "dep1@example.com")
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 150000, "currency": "INR"},  # Rs.1500.00 in paise
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["available_balance"] == 150000
    assert body["transaction_id"] is not None


def test_deposit_creates_balanced_ledger(client, db):
    headers, wallet_id = _make_user_and_wallet(client, "dep2@example.com")
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=headers,
    )
    txn_id = resp.json()["transaction_id"]

    entries = db.scalars(
        select(LedgerEntry).where(
            LedgerEntry.transaction_id == uuid.UUID(txn_id)
        )
    ).all()
    assert len(entries) == 2

    credits = sum(e.amount for e in entries if e.entry_type == EntryType.CREDIT)
    debits = sum(e.amount for e in entries if e.entry_type == EntryType.DEBIT)
    assert credits == debits == 100000  # the ledger nets to zero


def test_deposit_rejects_zero_amount(client):
    headers, wallet_id = _make_user_and_wallet(client, "dep3@example.com")
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 0, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_deposit_rejects_wrong_currency(client):
    headers, wallet_id = _make_user_and_wallet(client, "dep4@example.com")
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 100000, "currency": "USD"},  # wallet is INR
        headers=headers,
    )
    assert resp.status_code == 409


def test_deposit_requires_auth(client):
    headers, wallet_id = _make_user_and_wallet(client, "dep5@example.com")
    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 100000, "currency": "INR"},
    )
    assert resp.status_code == 401


def test_cannot_deposit_to_another_users_wallet(client):
    _, wallet_id = _make_user_and_wallet(client, "dep6a@example.com")
    headers_b, _ = _make_user_and_wallet(client, "dep6b@example.com")

    resp = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=headers_b,
    )
    assert resp.status_code == 404


def test_deposit_to_missing_wallet_returns_404(client):
    headers, _ = _make_user_and_wallet(client, "dep7@example.com")
    resp = client.post(
        f"/api/v1/wallets/{uuid.uuid4()}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_ledger_balance_invariant_after_multiple_deposits(client, db):
    """After N deposits: wallet balance == sum(CREDIT) - sum(DEBIT) for the wallet.

    This is the reconciliation invariant in miniature. For deposit-only the
    wallet has no debits, but we write it the general way so it stays correct
    once transfers/withdrawals add wallet debits in later phases.
    """
    headers, wallet_id = _make_user_and_wallet(client, "inv@example.com")
    amounts = [50000, 100000, 25000, 75000]

    for amount in amounts:
        client.post(
            f"/api/v1/wallets/{wallet_id}/deposit",
            json={"amount": amount, "currency": "INR"},
            headers=headers,
        )

    cached = client.get(
        f"/api/v1/wallets/{wallet_id}/balance", headers=headers
    ).json()["available_balance"]
    assert cached == sum(amounts)

    entries = db.scalars(
        select(LedgerEntry).where(LedgerEntry.wallet_id == uuid.UUID(wallet_id))
    ).all()
    credits = sum(e.amount for e in entries if e.entry_type == EntryType.CREDIT)
    debits = sum(e.amount for e in entries if e.entry_type == EntryType.DEBIT)
    assert credits - debits == cached
