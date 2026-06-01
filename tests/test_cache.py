import uuid

from app.cache.redis_cache import BalanceCache


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


# --- BalanceCache unit behavior (in-memory fake) ---

def test_cache_set_get_invalidate(fake_redis):
    cache = BalanceCache(fake_redis)
    wid = uuid.uuid4()

    assert cache.get(wid) is None
    cache.set(wid, {"available_balance": 500})
    assert cache.get(wid)["available_balance"] == 500
    cache.invalidate(wid)
    assert cache.get(wid) is None


def test_cache_degrades_gracefully_when_backend_down():
    class BrokenRedis:
        def get(self, key):
            raise RuntimeError("redis down")

        def setex(self, key, ttl, value):
            raise RuntimeError("redis down")

        def delete(self, *keys):
            raise RuntimeError("redis down")

    cache = BalanceCache(BrokenRedis())
    wid = uuid.uuid4()
    # none of these raise -> the API stays up even if Redis is unavailable
    assert cache.get(wid) is None
    cache.set(wid, {"available_balance": 1})
    cache.invalidate(wid)


# --- cache behavior through the API ---

def test_balance_cached_then_invalidated_on_write(client, fake_redis):
    headers = _auth(client, "cache1@example.com")
    wid = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/v1/wallets/{wid}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=headers,
    )

    key = f"wallet:balance:{wid}"
    assert fake_redis.get(key) is None  # writes don't populate, only reads do

    r1 = client.get(f"/api/v1/wallets/{wid}/balance", headers=headers)
    assert r1.json()["available_balance"] == 100000
    assert fake_redis.get(key) is not None  # populated on read

    # a write must bust the cache, or the next read would be stale
    client.post(
        f"/api/v1/wallets/{wid}/deposit",
        json={"amount": 50000, "currency": "INR"},
        headers=headers,
    )
    assert fake_redis.get(key) is None  # invalidated

    r2 = client.get(f"/api/v1/wallets/{wid}/balance", headers=headers)
    assert r2.json()["available_balance"] == 150000  # fresh, not stale


def test_cache_does_not_leak_across_users(client, fake_redis):
    h_owner = _auth(client, "owner@example.com")
    wid = client.post(
        "/api/v1/wallets", json={"currency": "INR"}, headers=h_owner
    ).json()["id"]
    client.post(
        f"/api/v1/wallets/{wid}/deposit",
        json={"amount": 100000, "currency": "INR"},
        headers=h_owner,
    )
    # owner reads -> wallet is now cached (with its user_id)
    client.get(f"/api/v1/wallets/{wid}/balance", headers=h_owner)
    assert fake_redis.get(f"wallet:balance:{wid}") is not None

    # a different user asking for the same wallet must not get a cache hit served
    h_intruder = _auth(client, "intruder@example.com")
    resp = client.get(f"/api/v1/wallets/{wid}/balance", headers=h_intruder)
    assert resp.status_code == 404
