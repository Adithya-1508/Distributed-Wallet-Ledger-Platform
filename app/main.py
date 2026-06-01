import logging

from fastapi import Depends, FastAPI, Response, status
from prometheus_client import make_asgi_app
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.middleware import ObservabilityMiddleware
from app.api.routes import auth, users, wallets
from app.core.logging import configure_logging
from app.db.session import get_db

configure_logging()
log = logging.getLogger("app")

app = FastAPI(title="Wallet Ledger Platform")
app.add_middleware(ObservabilityMiddleware)
app.mount("/metrics", make_asgi_app())  # Prometheus exposition

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(wallets.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: the process is up and serving."""
    return {"status": "ok"}


@app.get("/health/ready")
def readiness(
    response: Response, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Readiness probe: can we actually serve traffic (is the DB reachable)?"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception:
        log.warning("readiness check failed", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "db": "down"}
