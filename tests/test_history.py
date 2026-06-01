def _auth(client, email):
    client.post(
        "/api/v1/users",
        json={"name": "T", "email": email, "password": "supersecret"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "supersecret"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _wallet(client, headers, currency="INR"):
    return client.post(
        "/api/v1/wallets", json={"currency": currency}, headers=headers
    ).json()["id"]


def _deposit(client, headers, wallet_id, amount):
    client.post(
        f"/api/v1/wallets/{wallet_id}/deposit",
        json={"amount": amount, "currency": "INR"},
        headers=headers,
    )


def test_history_lists_entries_newest_first(client):
    headers = _auth(client, "h1@example.com")
    wid = _wallet(client, headers)
    _deposit(client, headers, wid, 1000)
    _deposit(client, headers, wid, 2000)
    client.post(
        f"/api/v1/wallets/{wid}/withdraw",
        json={"amount": 500, "currency": "INR"},
        headers=headers,
    )

    body = client.get(
        f"/api/v1/wallets/{wid}/transactions", headers=headers
    ).json()
    assert len(body["items"]) == 3
    # the withdrawal was last -> appears first (newest-first)
    assert body["items"][0]["entry_type"] == "DEBIT"
    assert body["items"][0]["amount"] == 500
    for item in body["items"]:
        assert item["currency"] == "INR"
        assert item["transaction_id"]


def test_history_pagination(client):
    headers = _auth(client, "h2@example.com")
    wid = _wallet(client, headers)
    for amount in (1000, 2000, 3000):
        _deposit(client, headers, wid, amount)

    page1 = client.get(
        f"/api/v1/wallets/{wid}/transactions?limit=2&offset=0", headers=headers
    ).json()
    assert len(page1["items"]) == 2
    assert page1["limit"] == 2
    assert page1["offset"] == 0

    page2 = client.get(
        f"/api/v1/wallets/{wid}/transactions?limit=2&offset=2", headers=headers
    ).json()
    assert len(page2["items"]) == 1


def test_history_requires_auth(client):
    headers = _auth(client, "h3@example.com")
    wid = _wallet(client, headers)
    assert client.get(f"/api/v1/wallets/{wid}/transactions").status_code == 401


def test_history_only_owner_can_read(client):
    h_owner = _auth(client, "h_owner@example.com")
    wid = _wallet(client, h_owner)
    _deposit(client, h_owner, wid, 1000)

    h_other = _auth(client, "h_other@example.com")
    resp = client.get(f"/api/v1/wallets/{wid}/transactions", headers=h_other)
    assert resp.status_code == 404


def test_history_shows_only_this_wallets_legs(client):
    h_a = _auth(client, "h_a@example.com")
    w_a = _wallet(client, h_a)
    _deposit(client, h_a, w_a, 100000)

    h_b = _auth(client, "h_b@example.com")
    w_b = _wallet(client, h_b)

    client.post(
        f"/api/v1/wallets/{w_a}/transfer",
        json={"recipient_wallet_id": w_b, "amount": 30000, "currency": "INR"},
        headers=h_a,
    )

    # sender sees the deposit (CREDIT) + the transfer leg (DEBIT)
    a_items = client.get(
        f"/api/v1/wallets/{w_a}/transactions", headers=h_a
    ).json()["items"]
    assert len(a_items) == 2
    assert {i["entry_type"] for i in a_items} == {"CREDIT", "DEBIT"}

    # recipient sees only the incoming transfer (CREDIT)
    b_items = client.get(
        f"/api/v1/wallets/{w_b}/transactions", headers=h_b
    ).json()["items"]
    assert len(b_items) == 1
    assert b_items[0]["entry_type"] == "CREDIT"
    assert b_items[0]["amount"] == 30000
