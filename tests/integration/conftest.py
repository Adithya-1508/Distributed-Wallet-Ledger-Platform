import pytest


@pytest.fixture(scope="session")
def kafka_bootstrap():
    """Spin up a throwaway Redpanda broker in Docker for the suite.

    Redpanda speaks the Kafka protocol, so the confluent-kafka client connects to
    it unchanged. Skips (rather than fails) if testcontainers isn't installed or
    Docker isn't reachable, so the rest of the suite still runs without Docker.
    """
    try:
        from testcontainers.redpanda import RedpandaContainer
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"testcontainers redpanda module not available: {exc}")

    try:
        container = RedpandaContainer()
        container.start()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"could not start Redpanda container (Docker required): {exc}")

    try:
        yield container.get_bootstrap_server()
    finally:
        container.stop()
