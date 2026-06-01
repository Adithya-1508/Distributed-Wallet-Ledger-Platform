from app.events.consumer import NotificationConsumer


def _payload(txn_id="txn-1"):
    return {
        "transaction_id": txn_id,
        "type": "DEPOSIT",
        "status": "COMPLETED",
        "currency": "INR",
        "amount": 1000,
        "wallet_id": "w-1",
        "counterparty_wallet_id": None,
    }


def test_consumer_handles_new_event():
    calls = []
    c = NotificationConsumer(consumer=None, topic="t", handler=calls.append)
    assert c.handle_event(_payload()) is True
    assert len(calls) == 1


def test_consumer_dedupes_duplicate_delivery():
    calls = []
    c = NotificationConsumer(consumer=None, topic="t", handler=calls.append)

    first = c.handle_event(_payload("txn-dup"))
    second = c.handle_event(_payload("txn-dup"))  # at-least-once re-delivery

    assert first is True
    assert second is False
    assert len(calls) == 1  # handled exactly once


def test_consumer_handles_distinct_events():
    calls = []
    c = NotificationConsumer(consumer=None, topic="t", handler=calls.append)
    c.handle_event(_payload("a"))
    c.handle_event(_payload("b"))
    assert len(calls) == 2


def test_default_handler_does_not_raise():
    c = NotificationConsumer(consumer=None, topic="t")
    assert c.handle_event(_payload()) is True
