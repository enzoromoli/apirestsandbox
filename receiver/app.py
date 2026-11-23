"""Récepteur des webhooks de sandboxd : vérifie la signature, l'horodatage et les doublons.

Lancement : SANDBOXD_WEBHOOK_SECRET=... .venv/bin/uvicorn receiver.app:app --port 9000
"""
import hashlib
import hmac
import json
import os
import time

from fastapi import FastAPI, Request, Response

SECRET = os.environ.get("SANDBOXD_WEBHOOK_SECRET", "")
MAX_AGE = 300
EVENTS: list[dict] = []
SEEN: set[str] = set()

app = FastAPI()


@app.post("/webhooks")
async def receive(request: Request):
    body = await request.body()
    timestamp = request.headers.get("webhook-timestamp", "")
    expected = "sha256=" + hmac.new(SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("webhook-signature", ""), expected):
        return Response("signature invalide", status_code=401)
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > MAX_AGE:
        return Response("horodatage trop vieux", status_code=400)
    event = json.loads(body)
    if event["id"] in SEEN:
        return {"status": "duplicate"}
    SEEN.add(event["id"])
    EVENTS.append(event)
    print(event["type"], event["data"]["id"], flush=True)
    return {"status": "ok"}
