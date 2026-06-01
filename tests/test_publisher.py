import json

import pytest

from app.events.publisher import OutboxPublisher
from app.repositories.outbox_repo import OutboxRepository


class FakeProducer:
    """A stand-in Kafka producer: records what was produced, reports success."""

    def __init__(self, fail: bool = False) -> None:
        self.produced: list[dict] = []
        self.flushed = False
        self._fail = fail

    def produce(self, *, topic, key, value, headers=None, on_delivery=None):
        self.produced.append(
            {"topic": topic, "key": key, "value": value, "headers": headers}
        )
        if on_delivery is not None:
            on_delivery("broker down" if self._fail else None, None)

    def flush(self, timeout=None):
        self.flushed = True
        return 0


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


def _deposit(client, headers, amount=100000):
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=headers
    ).json()["id"]
    return client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": amount, "currency": "INR"},
        headers=headers,
    ).json()["transaction_id"]


def test_publish_batch_sends_and_marks(client, db):
    headers = _register_and_login(client, "pub1@example.com")
    txn_id = _deposit(client, headers)

    fake = FakeProducer()
    published = OutboxPublisher(fake, topic="test.topic").publish_batch(db)

    assert published == 1
    assert fake.flushed is True
    assert len(fake.produced) == 1
    sent = json.loads(fake.produced[0]["value"])
    assert sent["transaction_id"] == txn_id
    assert sent["type"] == "DEPOSIT"
    assert fake.produced[0]["key"] == txn_id  # keyed by aggregate id
    # row is now stamped published -> nothing left to send
    assert OutboxRepository(db).fetch_unpublished() == []


def test_publish_batch_noop_when_empty(db):
    fake = FakeProducer()
    assert OutboxPublisher(fake, topic="test.topic").publish_batch(db) == 0
    assert fake.produced == []


def test_delivery_failure_leaves_event_unpublished(client, db):
    headers = _register_and_login(client, "pub2@example.com")
    _deposit(client, headers, amount=50000)

    fake = FakeProducer(fail=True)
    with pytest.raises(RuntimeError):
        OutboxPublisher(fake, topic="test.topic").publish_batch(db)

    # not marked -> it will be retried on the next loop (at-least-once)
    assert len(OutboxRepository(db).fetch_unpublished()) == 1
