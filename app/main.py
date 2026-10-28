"""sandboxd — squelette du TP4.

Le contrat (openapi.yaml) fait foi : FastAPI ne génère pas le sien.
Fournis : le client Docker (docker.py), les erreurs problem+json (errors.py),
le stockage en mémoire, la tâche de création en arrière-plan et getSandbox
pour exemple. À vous d'écrire les autres routes : voir le sujet, partie 2.
"""
import asyncio
import json
import secrets
import threading
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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


def get_ready_or_409(sandbox_id: str) -> dict:
    sb = get_or_404(sandbox_id)
    if sb["status"] != "ready":
        raise Problem(409, "not-ready", f"{sandbox_id} n'est pas prête")
    return sb


def check_path(path: str) -> None:
    """Refuse un chemin vide, absolu, trop long ou qui remonte avec '..' (422)."""
    if not path or len(path) > 4096 or path.startswith("/") or "\x00" in path or ".." in path.split("/"):
        raise Problem(422, "validation", f"path : chemin invalide ({path!r})")


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

class SandboxCreate(BaseModel):
    image: str
    ttl_seconds: int = 600

# ---------- exemple fourni ----------

@app.get("/v1/sandboxes/{sandbox_id}")
def get_sandbox(sandbox_id: str):
    return public(get_or_404(sandbox_id))


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/v1/sandboxes")
async def create_sandbox(request: Request):
    body = await read_json(request, SandboxCreate, ("application/json",))
    sb = {"id": new_id(), "image": body.image, "status": "pending", "ttl_seconds": body.ttl_seconds,
          "limits": {"cpus": 1, "memory_mb": 512}, "created_at": now(), "container_id": None}
    SANDBOXES[sb["id"]] = sb
    threading.Thread(target=provision, args=(sb["id"],), daemon=True).start()
    return JSONResponse(public(sb), status_code=202, headers={"Location": f"/v1/sandboxes/{sb['id']}"})


@app.get("/v1/sandboxes")
def list_sandboxes(status: str | None = None, page_size: int = 20, page_token: str = "0"):
    items = [public(sb) for sb in SANDBOXES.values() if status is None or sb["status"] == status]
    start = int(page_token)
    page = items[start:start + page_size]
    next_token = str(start + page_size) if start + page_size < len(items) else None
    return {"items": page, "next_page_token": next_token}


@app.delete("/v1/sandboxes/{sandbox_id}", status_code=204)
def delete_sandbox(sandbox_id: str):
    sb = get_or_404(sandbox_id)
    if sb["container_id"]:
        docker.remove_container(sb["container_id"])
    del SANDBOXES[sandbox_id]

    
# ---------- à vous ----------
# Une sandbox en mémoire est un dict :
#   {"id", "image", "status", "ttl_seconds", "limits": {"cpus", "memory_mb"},
#    "created_at", "container_id"}
#
# TODO createSandbox   POST   /v1/sandboxes                     -> 202 + Location
# TODO listSandboxes   GET    /v1/sandboxes                     -> 200, paginé
# TODO deleteSandbox   DELETE /v1/sandboxes/{sandbox_id}        -> 204
# Bonus updateSandbox  PATCH  /v1/sandboxes/{sandbox_id}        -> ETag et If-Match

MAX_FILE_SIZE = 1024 * 1024  # 1 Mio


class ExecRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cmd: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(30, ge=1, le=60)


@app.post("/v1/sandboxes/{sandbox_id}/exec")
async def exec_command(sandbox_id: str, request: Request):
    sb = get_ready_or_409(sandbox_id)
    body = await read_json(request, ExecRequest, ("application/json",))
    if "" in body.cmd:
        raise Problem(422, "validation", "cmd : les éléments ne peuvent pas être vides")
    # exec_command bloque jusqu'à la fin de la commande : on le lance dans un thread
    return await asyncio.to_thread(docker.exec_command, sb["container_id"], body.cmd, body.timeout_seconds)


@app.get("/v1/sandboxes/{sandbox_id}/files")
def read_file(sandbox_id: str, path: str):
    sb = get_ready_or_409(sandbox_id)
    check_path(path)
    data = docker.read_file(sb["container_id"], path)
    if data is None:
        raise Problem(404, "file-not-found", f"{path} n'existe pas")
    return Response(data, media_type="application/octet-stream")


@app.put("/v1/sandboxes/{sandbox_id}/files")
async def write_file(sandbox_id: str, path: str, request: Request):
    sb = get_ready_or_409(sandbox_id)
    check_path(path)
    ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype != "application/octet-stream":
        raise Problem(415, "unsupported-media-type", "attendu : application/octet-stream")
    data = await request.body()
    if len(data) > MAX_FILE_SIZE:
        raise Problem(413, "payload-too-large", "1 Mio au plus")
    created = await asyncio.to_thread(docker.write_file, sb["container_id"], path, data)
    return Response(status_code=201 if created else 204)
