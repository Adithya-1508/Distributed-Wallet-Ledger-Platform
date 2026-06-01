from functools import lru_cache

from app.cache.redis_cache import BalanceCache, build_redis_client


@lru_cache
def _shared_client():
    # One client/connection-pool for the process, built on first use.
    return build_redis_client()


def get_balance_cache() -> BalanceCache:
    """FastAPI dependency. Overridden in tests with an in-memory fake."""
    return BalanceCache(_shared_client())
