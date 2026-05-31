def test_register_user_success(client):
    resp = client.post(
        "api/v1/users",
        json ={"name": "Adithya", "email" : "adithya@example.com", "password": "supersecret"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "adithya@example.com"
    assert "id" in body
    
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_conflicts(client):
    payload = {"name" : "A", "email": "dup@example.com", "password": "supersecret"}
    assert client.post("api/v1/users", json=payload).status_code == 201
    assert client.post("api/v1/users", json=payload).status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/v1/users",
        json = {"name" : "A", "email" : "x@example.com", "password" : "short"} 
    )
    assert resp.status_code == 422
    
       