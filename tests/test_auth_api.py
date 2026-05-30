def _register(client, email="login@example.com", password="supersecret"):
    return client.post(
        "api/v1/users",
        json={"name": "A", "email": email, "password": password}
    )

def test_login_success_returns_token(client):
    _register(client)
    resp = client.post(
        "api/v1/auth/token",
        data={"username": "login@example.com", "password": "supersecret"}
    )    
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_401(client):
    _register(client)
    resp = client.post(
        "api/v1/auth/login",
        data={"username": "login@example.com", "password": "WRONG"}
    )    
    assert resp.status_code == 401

def test_me_requires_auth(client):
    assert client.get("api/v1/users/me").status_code == 401


def test_me_returns_current_user(client):
    _register(client, email="me@example.com")
    token =client.post(
        "api/v1/auth/login",
        data ={"username": "me@example.com", "password": "supersecret"},
    ).json()["access_token"]

    resp = client.get(
        "api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()['email'] == "me@example.com"
    assert "password_hash" not in resp.json()