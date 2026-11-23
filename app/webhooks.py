"""Webhooks : événements signés envoyés aux URL abonnées."""
import hashlib
import hmac
import json
import os
import threading
import time
import uuid

import httpx

URLS = [url for url in os.environ.get("SANDBOXD_WEBHOOK_URLS", "").split(",") if url]
SECRET = os.environ.get("SANDBOXD_WEBHOOK_SECRET", "")
if URLS and not SECRET:
    raise SystemExit("sandboxd : SANDBOXD_WEBHOOK_SECRET est obligatoire avec SANDBOXD_WEBHOOK_URLS.")
RETRY_DELAYS = [1, 2, 4, 8]


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def emit(event_type: str, sandbox: dict) -> None:
    body = json.dumps({"id": str(uuid.uuid4()), "type": event_type, "data": sandbox}).encode()
    for url in URLS:
        threading.Thread(target=deliver, args=(url, body), daemon=True).start()


def deliver(url: str, body: bytes) -> None:
    for delay in [0, *RETRY_DELAYS]:
        time.sleep(delay)
        timestamp = str(int(time.time()))
        headers = {"Content-Type": "application/json", "Webhook-Timestamp": timestamp,
                   "Webhook-Signature": sign(SECRET, timestamp, body)}
        try:
            if httpx.post(url, content=body, headers=headers, timeout=5).is_success:
                return
        except httpx.HTTPError:
            pass
