"""Journal d'audit : une ligne JSON par requête sur /v1."""
import json
import os
import threading
from datetime import datetime, timezone

from fastapi import Request

AUDIT_LOG = os.environ.get("SANDBOXD_AUDIT_LOG", "audit.log")
AUDIT_LOCK = threading.Lock()


def write(entry: dict) -> None:
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with AUDIT_LOCK, open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def action_name(request: Request) -> str | None:
    # Le nom de la fonction de la route, en camelCase, donne l'operationId : exec_command -> execCommand.
    route = request.scope.get("route")
    if route is None:
        return None
    first, *rest = route.name.split("_")
    return first + "".join(word.title() for word in rest)


def install(app) -> None:
    @app.middleware("http")
    async def audit(request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            action = action_name(request)
            entry = {
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "actor": getattr(request.state, "actor", {"role": "anonymous"}),
                "method": request.method,
                "path": request.url.path,
                "action": action,
                "sandbox_id": request.scope.get("path_params", {}).get("sandbox_id"),
                "status": status,
            }
            if action == "execCommand":
                entry["cmd"] = getattr(request.state, "cmd", None)
            if action in ("readFile", "writeFile"):
                entry["file_path"] = request.query_params.get("path")
            write(entry)
