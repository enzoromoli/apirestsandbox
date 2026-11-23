"""Le récepteur de webhooks : signature invalide, doublon, horodatage trop vieux."""
import json
import os
import time
import uuid

os.environ["SANDBOXD_WEBHOOK_SECRET"] = "secret-de-test"

from fastapi.testclient import TestClient  # noqa: E402

from app.webhooks import sign  # noqa: E402
from receiver import app as receiver  # noqa: E402

client = TestClient(receiver.app)


def send(event_id: str | None = None, age: int = 0, secret: str = "secret-de-test"):
    body = json.dumps({"id": event_id or str(uuid.uuid4()), "type": "sandbox.ready",
                       "data": {"id": "sbx-aaaaaaaa"}}).encode()
    timestamp = str(int(time.time()) - age)
    headers = {"Webhook-Timestamp": timestamp, "Webhook-Signature": sign(secret, timestamp, body)}
    return client.post("/webhooks", content=body, headers=headers)


def test_evenement_valide():
    r = send()
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_signature_invalide():
    assert send(secret="autre-secret").status_code == 401


def test_doublon():
    event_id = str(uuid.uuid4())
    assert send(event_id).json() == {"status": "ok"}
    assert send(event_id).json() == {"status": "duplicate"}
    assert [e["id"] for e in receiver.EVENTS].count(event_id) == 1


def test_horodatage_trop_vieux():
    assert send(age=600).status_code == 400
