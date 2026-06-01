import pytest


@pytest.fixture(scope="session")
def kafka_bootstrap():
    """Spin up a throwaway Kafka broker in Docker for the suite.

    Skips (rather than fails) if testcontainers isn't installed or Docker isn't
    reachable, so the rest of the suite still runs on machines without Docker.
    """
    try:
        from testcontainers.kafka import KafkaContainer
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"testcontainers[kafka] not available: {exc}")

    try:
        container = KafkaContainer()
        container.start()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"could not start Kafka container (Docker required): {exc}")

    try:
        yield container.get_bootstrap_server()
    finally:
        container.stop()
