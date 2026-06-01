import uuid

from app.db.models.wallet import Wallet
from app.services.reconciliation_service import ReconciliationService


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


def test_reconciliation_empty_db_is_ok(db):
    report = ReconciliationService(db).check()
    assert report.ok is True
    assert report.wallets_checked == 0


def test_reconciliation_clean_after_real_operations(client, db):
    h_a, w_a = _funded_wallet(client, "rec_a@example.com", 100000)
    h_b, w_b = _funded_wallet(client, "rec_b@example.com", 50000)

    client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 30000, "currency": "INR"},
        headers=h_a,
    )
    client.post(
        f"/api/v1/wallets/{w_b}/withdraw",
        json={"amount": 20000, "currency": "INR"},
        headers=h_b,
    )

    report = ReconciliationService(db).check()
    assert report.wallets_checked == 2
    assert report.ok is True
    assert report.discrepancies == []


def test_reconciliation_detects_balance_drift(client, db):
    """If the cached balance ever diverges from the ledger, reconciliation
    catches it and reports the exact gap."""
    _, wallet_id = _funded_wallet(client, "rec_drift@example.com", 100000)

    # Simulate a bug that corrupts the cached balance without a ledger entry.
    wallet = db.get(Wallet, uuid.UUID(wallet_id))
    wallet.available_balance = 999999
    db.flush()

    report = ReconciliationService(db).check()
    assert report.ok is False

    bad = [d for d in report.discrepancies if str(d.wallet_id) == wallet_id]
    assert len(bad) == 1
    assert bad[0].cached_balance == 999999
    assert bad[0].ledger_balance == 100000  # ledger is the source of truth
    assert bad[0].diff == 899999
