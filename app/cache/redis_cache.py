"""Redis-backed balance cache.

`BalanceCache` is duck-typed over the client (anything with get/setex/delete),
so tests can drive it with an in-memory fake. Every operation degrades
gracefully: if Redis is unreachable the API still works -- a cache miss just
falls through to the database. A stale balance is dangerous, so we *invalidate*
(delete) on writes rather than try to update the cached value, and keep a short
TTL as a backstop.
"""
import json
import logging
import uuid

from app.core.config import settings

log = logging.getLogger(__name__)


def build_redis_client():
    import redis  # lazy import so the module is usable without the driver

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


class BalanceCache:
    def __init__(self, client, ttl_seconds: int = 30) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(wallet_id) -> str:
        return f"wallet:balance:{wallet_id}"

    def get(self, wallet_id: uuid.UUID) -> dict | None:
        try:
            raw = self.client.get(self._key(wallet_id))
            return json.loads(raw) if raw else None
        except Exception:  # cache down -> treat as a miss
            log.warning("balance cache GET failed", exc_info=True)
            return None

    def set(self, wallet_id: uuid.UUID, payload: dict) -> None:
        try:
            self.client.setex(
                self._key(wallet_id), self.ttl_seconds, json.dumps(payload)
            )
        except Exception:
            log.warning("balance cache SET failed", exc_info=True)

    def invalidate(self, *wallet_ids: uuid.UUID) -> None:
        try:
            keys = [self._key(w) for w in wallet_ids if w is not None]
            if keys:
                self.client.delete(*keys)
        except Exception:
            log.warning("balance cache INVALIDATE failed", exc_info=True)
