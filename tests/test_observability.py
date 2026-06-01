def test_liveness(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readiness_ok_when_db_up(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"


def test_request_id_header_is_returned(client):
    r = client.get("/health")
    assert r.headers.get("X-Request-ID")  # minted when none supplied


def test_request_id_header_is_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert r.headers["X-Request-ID"] == "trace-abc-123"


def test_metrics_endpoint_exposes_request_counter(client):
    client.get("/health")  # generate at least one observed request
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
