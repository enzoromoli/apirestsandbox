"""sandboxd — squelette du TP4.

Le contrat (openapi.yaml) fait foi : FastAPI ne génère pas le sien.
Fournis : le client Docker (docker.py), les erreurs problem+json (errors.py),
le stockage en mémoire, la tâche de création en arrière-plan et getSandbox
pour exemple. À vous d'écrire les autres routes : voir le sujet, partie 2.
"""
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from . import docker
from .errors import Problem, install

app = FastAPI(title="sandboxd", openapi_url=None, docs_url=None, redoc_url=None)
install(app)

SANDBOXES: dict[str, dict] = {}  # id -> sandbox (en mémoire : perdue au redémarrage)
LOCK = threading.Lock()


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(d: datetime) -> str:
    return d.isoformat().replace("+00:00", "Z")


def new_id() -> str:
    return "sbx-" + secrets.token_hex(4)


def public(sb: dict) -> dict:
    """La représentation JSON d'une sandbox, conforme au schéma Sandbox."""
    return {
        "id": sb["id"], "image": sb["image"], "status": sb["status"], "ttl_seconds": sb["ttl_seconds"],
        "limits": sb["limits"], "created_at": iso(sb["created_at"]),
        "expires_at": iso(sb["created_at"] + timedelta(seconds=sb["ttl_seconds"])),
    }


def get_or_404(sandbox_id: str) -> dict:
    sb = SANDBOXES.get(sandbox_id)
    if sb is None:
        raise Problem(404, "not-found", f"{sandbox_id} n'existe pas")
    return sb


async def read_json(request: Request, model: type[BaseModel], media_types: tuple[str, ...]) -> BaseModel:
    """Lit le corps : Content-Type refusé (415), JSON invalide (400), contenu invalide (422)."""
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype not in media_types:
        raise Problem(415, "unsupported-media-type", f"attendu : {', '.join(media_types)}")
    try:
        data = json.loads(await request.body())
    except ValueError:
        raise Problem(400, "invalid-json", "le corps n'est pas du JSON valide")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise Problem(422, "validation", f"{'.'.join(map(str, first['loc'])) or 'corps'} : {first['msg']}")


def provision(sandbox_id: str) -> None:
    """Tâche de fond : crée le conteneur, puis passe la sandbox en ready ou failed.

    À lancer depuis createSandbox, après avoir répondu 202 :
        threading.Thread(target=provision, args=(sandbox_id,), daemon=True).start()
    """
    sb = SANDBOXES.get(sandbox_id)
    if sb is None:
        return
    try:
        cid = docker.create_container(sb["image"], sb["limits"]["cpus"], sb["limits"]["memory_mb"],
                                      {"sandboxd": "1", "sandboxd.id": sandbox_id})
        with LOCK:
            if sandbox_id not in SANDBOXES:  # détruite entre-temps
                docker.remove_container(cid)
                return
            sb.update(container_id=cid, status="ready")
    except docker.DockerError:
        sb.update(status="failed")


# ---------- exemple fourni ----------

@app.get("/v1/sandboxes/{sandbox_id}")
def get_sandbox(sandbox_id: str):
    return public(get_or_404(sandbox_id))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ---------- à vous ----------
# Une sandbox en mémoire est un dict :
#   {"id", "image", "status", "ttl_seconds", "limits": {"cpus", "memory_mb"},
#    "created_at", "container_id"}
#
# TODO createSandbox   POST   /v1/sandboxes                     -> 202 + Location
# TODO listSandboxes   GET    /v1/sandboxes                     -> 200, paginé
# TODO deleteSandbox   DELETE /v1/sandboxes/{sandbox_id}        -> 204
# TODO execCommand     POST   /v1/sandboxes/{sandbox_id}/exec   -> docker.exec_command(...)
# TODO readFile        GET    /v1/sandboxes/{sandbox_id}/files  -> docker.read_file(...)
# TODO writeFile       PUT    /v1/sandboxes/{sandbox_id}/files  -> docker.write_file(...)
# Bonus updateSandbox  PATCH  /v1/sandboxes/{sandbox_id}        -> ETag et If-Match
