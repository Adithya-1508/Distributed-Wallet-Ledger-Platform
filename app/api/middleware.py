"""Observability middleware: request id + access log + metrics, in one pass."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import request_id_var
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

log = logging.getLogger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Reuse an inbound request id (e.g. from a gateway) or mint one.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        duration_s = time.perf_counter() - start

        # Use the route template (e.g. /api/v1/wallets/{wallet_id}/balance) not
        # the raw path, so metrics labels stay low-cardinality.
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)

        if path != "/metrics":  # don't let scrapes count themselves
            REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(duration_s)
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(duration_s * 1000, 2),
                },
            )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
