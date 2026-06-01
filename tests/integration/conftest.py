import pytest


@pytest.fixture(scope="session")
def kafka_bootstrap():
    """Spin up a throwaway Kafka-protocol broker in Docker for the suite.

    The app, compose, and deploy all run Redpanda -- but Redpanda and Kafka are
    the SAME wire protocol, so exercising the confluent-kafka client against a
    Kafka broker here proves the client wiring just as well, and KafkaContainer
    is the broker module testcontainers actually ships. Skips (rather than fails)
    if testcontainers isn't installed or Docker isn't reachable.
    """
    try:
        from testcontainers.kafka import KafkaContainer
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"testcontainers kafka module not available: {exc}")

    try:
        container = KafkaContainer()
        container.start()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"could not start broker container (Docker required): {exc}")

    try:
        yield container.get_bootstrap_server()
    finally:
        container.stop()
