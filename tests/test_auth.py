"""Authentification et autorisation de sandboxd, sans Docker."""
import os
from datetime import datetime, timedelta, timezone

SECRET = "secret-de-test-assez-long-pour-hs256"
os.environ["SANDBOXD_API_KEY"] = "test-key"
os.environ["SANDBOXD_JWT_SECRET"] = SECRET

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import docker, main  # noqa: E402

A, B, ABSENT = "sbx-aaaaaaaa", "sbx-bbbbbbbb", "sbx-00000000"
OPERATOR = {"Authorization": "Bearer test-key"}
EXEC = {"json": {"cmd": ["echo", "ok"]}}
FILE = {"content": b"x", "headers": {"Content-Type": "application/octet-stream"}}

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fake_docker(monkeypatch):
    monkeypatch.setattr(docker, "ping", lambda: True)
    monkeypatch.setattr(docker, "create_container", lambda *args: "cid-new")
    monkeypatch.setattr(docker, "remove_container", lambda cid: None)
    monkeypatch.setattr(docker, "exec_command", lambda cid, cmd, timeout: {
        "exit_code": 0, "stdout": "ok\n", "stderr": "", "duration_ms": 1, "timed_out": False, "truncated": False})
    monkeypatch.setattr(docker, "read_file", lambda cid, path: b"contenu")
    monkeypatch.setattr(docker, "write_file", lambda cid, path, data: True)
    main.SANDBOXES.clear()
    main.IDEMPOTENCY.clear()
    for sid in (A, B):
        main.SANDBOXES[sid] = {"id": sid, "image": "alpine:3.20", "status": "ready", "ttl_seconds": 600,
                               "limits": {"cpus": 1, "memory_mb": 512}, "created_at": main.now(),
                               "container_id": "cid-" + sid}


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def token(sandbox_id: str = A, secret: str = SECRET, algorithm: str = "HS256", **claims) -> str:
    now = datetime.now(timezone.utc)
    body = {"sub": sandbox_id, "role": "agent", "iat": now, "exp": now + timedelta(minutes=15), **claims}
    return jwt.encode(body, secret, algorithm=algorithm)


def agent(sandbox_id: str = A) -> dict:
    r = client.post(f"/v1/sandboxes/{sandbox_id}/tokens", headers=OPERATOR)
    assert r.status_code == 201
    return bearer(r.json()["token"])


SANDBOX_ROUTES = [
    ("GET", "/v1/sandboxes/{id}", {}),
    ("POST", "/v1/sandboxes/{id}/exec", EXEC),
    ("GET", "/v1/sandboxes/{id}/files?path=notes.txt", {}),
    ("PUT", "/v1/sandboxes/{id}/files?path=notes.txt", FILE),
]
OPERATOR_ROUTES = [
    ("GET", "/v1/sandboxes", {}),
    ("POST", "/v1/sandboxes", {"json": {"image": "alpine:3.20"}}),
    ("PATCH", f"/v1/sandboxes/{A}", {"json": {"ttl_seconds": 900},
                                     "headers": {"Content-Type": "application/merge-patch+json"}}),
    ("DELETE", f"/v1/sandboxes/{A}", {}),
    ("POST", f"/v1/sandboxes/{A}/tokens", {}),
]
ALL_ROUTES = OPERATOR_ROUTES + [(m, u.format(id=A), kw) for m, u, kw in SANDBOX_ROUTES]


def with_headers(kwargs: dict, headers: dict) -> dict:
    return {**kwargs, "headers": {**kwargs.get("headers", {}), **headers}}


@pytest.mark.parametrize("method,url,kwargs", ALL_ROUTES)
def test_sans_en_tete_401(method, url, kwargs):
    r = client.request(method, url, **kwargs)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    assert r.headers["Content-Type"] == "application/problem+json"


@pytest.mark.parametrize("authorization", [
    "Bearer mauvaise-cle",
    "Bearer test-key-en-trop",
    "Basic dGVzdDp0ZXN0LWtleQ==",
    "Basic test-key",
    "test-key",
    "Bearer ",
])
def test_mauvais_identifiant_401(authorization):
    r = client.get(f"/v1/sandboxes/{A}", headers={"Authorization": authorization})
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("bad_token", [
    token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)),
    token(secret="un-autre-secret-assez-long-pour-hs256"),
    token(secret=None, algorithm="none"),
    token(role="operator"),
    token(role="admin"),
    jwt.encode({"sub": A, "role": "agent"}, SECRET, algorithm="HS256"),
    "pas.un.jwt",
], ids=["expire", "autre-secret", "alg-none", "role-operator", "role-admin", "sans-exp", "illisible"])
def test_jeton_invalide_401(bad_token):
    r = client.get(f"/v1/sandboxes/{A}", headers=bearer(bad_token))
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_jeton_expire_message():
    r = client.get(f"/v1/sandboxes/{A}", headers=bearer(token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))))
    assert r.json()["detail"] == "jeton expiré"


@pytest.mark.parametrize("method,url,kwargs", ALL_ROUTES)
def test_operateur_partout(method, url, kwargs):
    r = client.request(method, url, **with_headers(kwargs, OPERATOR))
    assert r.status_code < 300, r.text


@pytest.mark.parametrize("method,url,kwargs", SANDBOX_ROUTES)
def test_agent_sur_sa_sandbox(method, url, kwargs):
    r = client.request(method, url.format(id=A), **with_headers(kwargs, agent(A)))
    assert r.status_code < 300, r.text


@pytest.mark.parametrize("method,url,kwargs", SANDBOX_ROUTES)
def test_agent_sur_une_autre_sandbox_404(method, url, kwargs):
    other = client.request(method, url.format(id=B), **with_headers(kwargs, agent(A)))
    del main.SANDBOXES[B]
    missing = client.request(method, url.format(id=B), **with_headers(kwargs, OPERATOR))
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert other.headers["Content-Type"] == missing.headers["Content-Type"]


@pytest.mark.parametrize("method,url,kwargs", OPERATOR_ROUTES)
def test_agent_sur_route_operateur_403(method, url, kwargs):
    r = client.request(method, url, **with_headers(kwargs, agent(A)))
    assert r.status_code == 403
    assert r.json()["type"] == "/problems/forbidden"
    assert A in main.SANDBOXES


def test_jeton_pour_sandbox_inexistante_404():
    r = client.post(f"/v1/sandboxes/{ABSENT}/tokens", headers=OPERATOR)
    assert r.status_code == 404


def test_jeton_d_une_sandbox_supprimee_404():
    headers = agent(A)
    assert client.delete(f"/v1/sandboxes/{A}", headers=OPERATOR).status_code == 204
    assert client.get(f"/v1/sandboxes/{A}", headers=headers).status_code == 404


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a/../../x", "..", "a/.."])
@pytest.mark.parametrize("method,kwargs", [("GET", {}), ("PUT", FILE)])
@pytest.mark.parametrize("who", ["operateur", "agent"])
def test_chemin_dangereux_422(path, method, kwargs, who):
    headers = OPERATOR if who == "operateur" else agent(A)
    r = client.request(method, f"/v1/sandboxes/{A}/files", params={"path": path}, **with_headers(kwargs, headers))
    assert r.status_code == 422


@pytest.mark.parametrize("url", ["/healthz", "/readyz"])
def test_sondes_sans_en_tete_200(url):
    assert client.get(url).status_code == 200
