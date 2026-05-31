
def _auth_headers(client, email="w@example.com", password="supersecret"):
    client.post(
        "/api/v1/users",
        json={"name": "A", "email": email, "password": password}
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_wallet_success(client):
    headers = _auth_headers(client)
    resp = client.post("/api/v1/wallets", json={"currency": "INR"}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["currency"] == "INR"
    assert body["available_balance"] == 0
    assert body["locked_balance"] == 0

def test_create_wallet_requires_auth(client):
    assert client.post("/api/v1/wallets", json={"currency": "INR"}).status_code == 401


def test_duplicate_currency_value_conflicts(client):
    headers = _auth_headers(client)
    assert client.post("/api/v1/wallets", json={"currency": "INR"}, headers=headers).status_code == 201
    assert client.post("/api/v1/wallets", json={"currency": "INR"}, headers=headers).status_code == 409


def test_get_balance_success(client):
    headers = _auth_headers(client)
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=headers
    ).json()['id']
    resp = client.get(f"/api/v1/wallets/{wallet_id}/balance",headers=headers)
    assert resp.status_code == 200
    assert resp.json()["available_balance"] == 0

def test_cannot_read_another_users_wallet(client):
    headers_a = _auth_headers(client, email="alice@example.com")
    wallet_id = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers= headers_a
    ).json()["id"]
    headers_b = _auth_headers(client, email="bob@example.com")
    resp = client.get(
        f"/api/v1/wallets/{wallet_id}/balance", headers= headers_b
    )
    assert resp.status_code == 404
