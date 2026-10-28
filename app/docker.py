"""Client minimal de l'API Docker Engine, sur le socket Unix.

Fourni par le starter kit : vous n'avez pas à le modifier pour le TP4.
Chaque fonction correspond à un ou plusieurs appels HTTP vus en journée 1.
"""
import io
import os
import struct
import tarfile
import time

import httpx

SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
WORKSPACE = "/workspace"
MAX_OUTPUT = 1024 * 1024  # 1 Mo par flux

_client = httpx.Client(
    transport=httpx.HTTPTransport(uds=SOCKET),
    base_url="http://docker",
    timeout=httpx.Timeout(10.0, read=70.0),
)


class DockerError(Exception):
    """Le démon Docker a répondu par une erreur, ou ne répond pas."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _check(r: httpx.Response) -> httpx.Response:
    if r.status_code >= 400:
        try:
            message = r.json().get("message", r.text)
        except ValueError:
            message = r.text
        raise DockerError(r.status_code, message)
    return r


def ping() -> bool:
    """GET /_ping : le démon répond-il ?"""
    try:
        return _client.get("/_ping", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def pull_image(image: str) -> None:
    """POST /images/create : télécharge l'image si elle manque."""
    name, _, tag = image.partition(":")
    with _client.stream("POST", "/images/create", params={"fromImage": name, "tag": tag or "latest"}, timeout=300.0) as r:
        _check(r)
        for _ in r.iter_bytes():
            pass


def create_container(image: str, cpus: float, memory_mb: int, labels: dict[str, str]) -> str:
    """POST /containers/create, puis /start. Renvoie l'identifiant du conteneur.

    Le conteneur reste vivant (sleep infinity) et travaille dans /workspace.
    Le durcissement (réseau coupé, utilisateur non root…) viendra au TP6.
    """
    body = {
        "Image": image,
        "Cmd": ["sleep", "infinity"],
        "WorkingDir": WORKSPACE,
        "Labels": labels,
        "HostConfig": {
            "NanoCpus": int(cpus * 1_000_000_000),
            "Memory": memory_mb * 1024 * 1024,
        },
    }
    r = _client.post("/containers/create", json=body)
    if r.status_code == 404:  # image absente : on la télécharge, puis on réessaie
        pull_image(image)
        r = _client.post("/containers/create", json=body)
    cid = _check(r).json()["Id"]
    _check(_client.post(f"/containers/{cid}/start"))
    return cid


def container_state(cid: str) -> str | None:
    """GET /containers/{id}/json : 'running', 'exited'… ou None s'il n'existe plus."""
    r = _client.get(f"/containers/{cid}/json")
    if r.status_code == 404:
        return None
    return _check(r).json()["State"]["Status"]


def remove_container(cid: str) -> None:
    """DELETE /containers/{id}?force=true. Ne dit rien s'il n'existe déjà plus."""
    r = _client.delete(f"/containers/{cid}", params={"force": "true"})
    if r.status_code != 404:
        _check(r)


def _demux(raw: bytes) -> tuple[bytes, bytes]:
    """Sépare stdout et stderr du flux multiplexé (en-tête de 8 octets par bloc)."""
    out, err = bytearray(), bytearray()
    i = 0
    while i + 8 <= len(raw):
        stream, size = struct.unpack(">BxxxL", raw[i:i + 8])
        chunk = raw[i + 8:i + 8 + size]
        (err if stream == 2 else out).extend(chunk)
        i += 8 + size
    return bytes(out), bytes(err)


def exec_command(cid: str, cmd: list[str], timeout_seconds: int) -> dict:
    """POST /containers/{id}/exec, /exec/{id}/start, puis GET /exec/{id}/json.

    La commande est lancée sous `timeout -s KILL` dans le conteneur : elle ne
    peut pas dépasser timeout_seconds. Renvoie un dict au format ExecResult.
    """
    started = time.monotonic()
    create = {
        "Cmd": ["timeout", "-s", "KILL", str(timeout_seconds), *cmd],
        "AttachStdout": True,
        "AttachStderr": True,
        "WorkingDir": WORKSPACE,
    }
    exec_id = _check(_client.post(f"/containers/{cid}/exec", json=create)).json()["Id"]

    raw = bytearray()
    truncated = False
    with _client.stream("POST", f"/exec/{exec_id}/start", json={"Detach": False, "Tty": False},
                        timeout=httpx.Timeout(10.0, read=timeout_seconds + 10)) as r:
        _check(r)
        for chunk in r.iter_bytes():
            if len(raw) < 2 * MAX_OUTPUT + 64:
                raw.extend(chunk)
            else:
                truncated = True

    info = _check(_client.get(f"/exec/{exec_id}/json")).json()
    stdout, stderr = _demux(bytes(raw))
    if len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT:
        truncated = True
    exit_code = info.get("ExitCode")
    duration_ms = int((time.monotonic() - started) * 1000)
    timed_out = exit_code == 137 and duration_ms >= timeout_seconds * 1000
    return {
        "exit_code": None if timed_out else exit_code,
        "stdout": stdout[:MAX_OUTPUT].decode("utf-8", "replace"),
        "stderr": stderr[:MAX_OUTPUT].decode("utf-8", "replace"),
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "truncated": truncated,
    }


def read_file(cid: str, path: str) -> bytes | None:
    """GET /containers/{id}/archive : renvoie le contenu, ou None si absent.

    Attention : `path` n'est pas encore vérifié (rendez-le sûr au TP6).
    """
    r = _client.get(f"/containers/{cid}/archive", params={"path": f"{WORKSPACE}/{path}"})
    if r.status_code == 404:
        return None
    _check(r)
    with tarfile.open(fileobj=io.BytesIO(r.content)) as tar:
        member = tar.next()
        if member is None or not member.isfile():
            return None
        return tar.extractfile(member).read()


def write_file(cid: str, path: str, data: bytes) -> bool:
    """PUT /containers/{id}/archive : écrit le fichier. Renvoie True s'il a été créé.

    Attention : `path` n'est pas encore vérifié (rendez-le sûr au TP6).
    """
    existed = read_file(cid, path) is not None
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=path)
        info.size = len(data)
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(data))
    r = _client.put(f"/containers/{cid}/archive", params={"path": WORKSPACE}, content=buf.getvalue(),
                    headers={"Content-Type": "application/x-tar"})
    _check(r)
    return not existed
