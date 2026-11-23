"""Exploitation : métriques RED sur /metrics et une ligne de log JSON par requête, avec un request_id."""
import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS = Counter("http_requests_total", "Requêtes HTTP", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "Durée des requêtes HTTP", ["method", "route"])
SANDBOXES_ACTIVE = Gauge("sandboxes_active", "Sandboxes en état pending ou ready")


def install(app, count_active) -> None:
    SANDBOXES_ACTIVE.set_function(count_active)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            duration = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", "inconnue")
            REQUESTS.labels(request.method, route, str(status)).inc()
            DURATION.labels(request.method, route).observe(duration)
            print(json.dumps({
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "level": "error" if status >= 500 else "info",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": round(duration * 1000),
            }), flush=True)
