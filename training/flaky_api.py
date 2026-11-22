"""API d'entraînement capricieuse pour le TP4. Fournie : ne pas modifier.

Une fausse sandboxd, en mémoire et sans Docker, qui respecte le contrat v1
mais se comporte mal exprès :
- 500 sandboxes déjà présentes, servies par pages de 20 au plus ;
- des 429 et des 503 au hasard, avec Retry-After ;
- des réponses lentes, qui dépassent un timeout raisonnable ;
- des réponses perdues : la création est faite, mais le client reçoit un 502.

Réglages par variables d'environnement : FLAKY_FAIL (0.2), FLAKY_SLOW (0.1),
FLAKY_LOST (0.15), FLAKY_SEED (pour rejouer le même scénario).
Compteurs : GET /_stats.
"""
import asyncio
import base64
import json
import os
import random
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

FAIL = float(os.environ.get("FLAKY_FAIL", "0.2"))
SLOW = float(os.environ.get("FLAKY_SLOW", "0.1"))
LOST = float(os.environ.get("FLAKY_LOST", "0.15"))
SLOW_SECONDS = 4
PAGE_MAX = 20
rng = random.Random(os.environ.get("FLAKY_SEED"))

app = FastAPI(title="flaky sandboxd", openapi_url=None, docs_url=None, redoc_url=None)
SANDBOXES: dict[str, dict] = {}
IDEMPOTENCY: dict[str, tuple[str, str]] = {}
STATS = {"requests": 0, "fail_429": 0, "fail_503": 0, "slow": 0, "lost": 0, "created": 0, "idempotent_replays": 0}

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
for i in range(500):
    sid = f"sbx-{i:08x}"
    SANDBOXES[sid] = {"id": sid, "image": "python:3.12-slim", "status": "ready" if i % 7 else "terminated",
                      "ttl_seconds": 900, "limits": {"cpus": 1, "memory_mb": 512},
                      "created_at": T0 + timedelta(minutes=i), "ready_at": 0.0}


def iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def public(sb: dict) -> dict:
    if sb["status"] == "pending" and time.monotonic() >= sb["ready_at"]:
        sb["status"] = "ready"
    return {"id": sb["id"], "image": sb["image"], "status": sb["status"], "ttl_seconds": sb["ttl_seconds"],
            "limits": sb["limits"], "created_at": iso(sb["created_at"]),
            "expires_at": iso(sb["created_at"] + timedelta(seconds=sb["ttl_seconds"]))}


def problem(status: int, slug: str, detail: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"type": f"/errors/{slug}", "title": slug, "status": status, "detail": detail},
                        status_code=status, media_type="application/problem+json", headers=headers)


@app.middleware("http")
async def chaos(request: Request, call_next):
    if request.url.path == "/_stats":
        return await call_next(request)
    STATS["requests"] += 1
    roll = rng.random()
    if roll < FAIL / 2:
        STATS["fail_429"] += 1
        return problem(429, "rate-limited", "trop de requêtes", {"Retry-After": "2"})
    if roll < FAIL:
        STATS["fail_503"] += 1
        return problem(503, "unavailable", "service momentanément indisponible", {"Retry-After": "1"})
    if roll < FAIL + SLOW:
        STATS["slow"] += 1
        await asyncio.sleep(SLOW_SECONDS)
    return await call_next(request)


@app.get("/_stats")
def stats():
    return {**STATS, "sandboxes": len(SANDBOXES)}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/v1/sandboxes")
def list_sandboxes(status: str | None = None, page_size: int = 20, page_token: str | None = None):
    page_size = max(1, min(page_size, PAGE_MAX))
    items = sorted(SANDBOXES.values(), key=lambda s: (s["created_at"], s["id"]), reverse=True)
    if status:
        items = [s for s in items if public(s)["status"] == status]
    start = 0
    if page_token:
        try:
            after = json.loads(base64.urlsafe_b64decode(page_token.encode()))["after"]
            start = next(i for i, s in enumerate(items) if s["id"] == after) + 1
        except Exception:
            return problem(400, "invalid-page-token", "jeton de page inconnu")
    page = items[start:start + page_size]
    more = start + page_size < len(items)
    token = base64.urlsafe_b64encode(json.dumps({"after": page[-1]["id"]}).encode()).decode() if more and page else None
    return {"items": [public(s) for s in page], "next_page_token": token}


@app.post("/v1/sandboxes", status_code=202)
async def create_sandbox(request: Request, idempotency_key: str | None = Header(None)):
    raw = await request.body()
    try:
        body = json.loads(raw)
        image = body["image"]
    except Exception:
        return problem(422, "validation", "corps invalide : image attendue")
    if idempotency_key and idempotency_key in IDEMPOTENCY:
        seen, sid = IDEMPOTENCY[idempotency_key]
        if seen != raw.decode(errors="replace"):
            return problem(422, "idempotency-key-reused", "même clé, corps différent")
        STATS["idempotent_replays"] += 1
        return JSONResponse(public(SANDBOXES[sid]), status_code=202, headers={"Location": f"/v1/sandboxes/{sid}"})
    sid = "sbx-" + secrets.token_hex(4)
    SANDBOXES[sid] = {"id": sid, "image": image, "status": "pending", "ttl_seconds": body.get("ttl_seconds", 900),
                      "limits": {"cpus": 1, "memory_mb": 512}, "created_at": datetime.now(timezone.utc).replace(microsecond=0),
                      "ready_at": time.monotonic() + 3}
    STATS["created"] += 1
    if idempotency_key:
        IDEMPOTENCY[idempotency_key] = (raw.decode(errors="replace"), sid)
    if rng.random() < LOST:  # la sandbox est créée, mais la réponse se perd
        STATS["lost"] += 1
        return problem(502, "bad-gateway", "réponse perdue en route")
    return JSONResponse(public(SANDBOXES[sid]), status_code=202, headers={"Location": f"/v1/sandboxes/{sid}"})


@app.get("/v1/sandboxes/{sandbox_id}")
def get_sandbox(sandbox_id: str):
    sb = SANDBOXES.get(sandbox_id)
    return public(sb) if sb else problem(404, "not-found", f"{sandbox_id} n'existe pas")


@app.delete("/v1/sandboxes/{sandbox_id}")
def delete_sandbox(sandbox_id: str):
    if SANDBOXES.pop(sandbox_id, None) is None:
        return problem(404, "not-found", f"{sandbox_id} n'existe pas")
    return Response(status_code=204)


@app.post("/v1/sandboxes/{sandbox_id}/exec")
async def exec_command(sandbox_id: str, request: Request):
    sb = SANDBOXES.get(sandbox_id)
    if sb is None:
        return problem(404, "not-found", f"{sandbox_id} n'existe pas")
    if public(sb)["status"] != "ready":
        return problem(409, "not-ready", f"{sandbox_id} n'est pas prête")
    cmd = (json.loads(await request.body()) or {}).get("cmd") or []
    return {"exit_code": 0, "stdout": " ".join(cmd) + "\n", "stderr": "", "duration_ms": 5,
            "timed_out": False, "truncated": False}
