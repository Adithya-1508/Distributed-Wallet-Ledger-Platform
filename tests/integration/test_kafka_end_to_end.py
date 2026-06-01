"""End-to-end: a money operation's outbox event actually flows through Kafka.

Requires Docker (Kafka via testcontainers). Run just these with:
    uv run pytest -m integration
Skip them with:
    uv run pytest -m "not integration"
"""
import json
import time
import uuid

import pytest

pytestmark = pytest.mark.integration


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


def test_deposit_event_reaches_kafka(client, db, kafka_bootstrap):
    from confluent_kafka import Consumer, Producer

    from app.events.publisher import OutboxPublisher

    topic = f"test.transactions.{uuid.uuid4().hex[:8]}"

    # 1. A deposit writes a ledger txn + an outbox row (same db session).
    headers = _register_and_login(client, "e2e@example.com")
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=headers
    ).json()["id"]
    txn_id = client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": 123456, "currency": "INR"},
        headers=headers,
    ).json()["transaction_id"]

    # 2. The publisher drains the outbox to the real (testcontainers) broker.
    producer = Producer({"bootstrap.servers": kafka_bootstrap})
    assert OutboxPublisher(producer, topic=topic).publish_batch(db) == 1

    # 3. A consumer reads it back off Kafka.
    consumer = Consumer(
        {
            "bootstrap.servers": kafka_bootstrap,
            "group.id": f"test-grp-{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])

    payload = None
    deadline = time.time() + 30
    while time.time() < deadline and payload is None:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        payload = json.loads(msg.value())
    consumer.close()

    assert payload is not None, "did not receive the event from Kafka in time"
    assert payload["transaction_id"] == txn_id
    assert payload["type"] == "DEPOSIT"
    assert payload["amount"] == 123456
