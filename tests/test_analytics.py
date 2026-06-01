import uuid

from app.repositories.stats_repo import TransactionStatRepository
from app.services.analytics_service import AnalyticsService


def _event(txn_id=None, *, type="DEPOSIT", currency="INR", amount=1000):
    return {
        "transaction_id": txn_id or str(uuid.uuid4()),
        "type": type,
        "status": "COMPLETED",
        "currency": currency,
        "amount": amount,
        "wallet_id": "w-1",
        "counterparty_wallet_id": None,
    }


def test_analytics_aggregates_count_and_total(db):
    svc = AnalyticsService(db)
    assert svc.handle_event(_event(amount=1000)) is True
    assert svc.handle_event(_event(amount=2500)) is True

    stat = TransactionStatRepository(db).get("INR", "DEPOSIT")
    assert stat.count == 2
    assert stat.total_amount == 3500


def test_analytics_is_idempotent(db):
    svc = AnalyticsService(db)
    txn_id = str(uuid.uuid4())

    assert svc.handle_event(_event(txn_id, amount=5000)) is True
    assert svc.handle_event(_event(txn_id, amount=5000)) is False  # re-delivery

    stat = TransactionStatRepository(db).get("INR", "DEPOSIT")
    assert stat.count == 1  # counted once despite two deliveries
    assert stat.total_amount == 5000


def test_analytics_separates_type_and_currency(db):
    svc = AnalyticsService(db)
    svc.handle_event(_event(type="DEPOSIT", currency="INR", amount=1000))
    svc.handle_event(_event(type="WITHDRAWAL", currency="INR", amount=400))
    svc.handle_event(_event(type="DEPOSIT", currency="USD", amount=900))

    repo = TransactionStatRepository(db)
    assert repo.get("INR", "DEPOSIT").total_amount == 1000
    assert repo.get("INR", "WITHDRAWAL").total_amount == 400
    assert repo.get("USD", "DEPOSIT").total_amount == 900
    assert repo.get("USD", "WITHDRAWAL") is None
