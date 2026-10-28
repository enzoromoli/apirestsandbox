"""Erreurs au format problem+json (RFC 9457). Fourni par le starter kit."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

TITLES = {
    400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
    412: "Precondition Failed", 413: "Payload Too Large", 415: "Unsupported Media Type",
    422: "Unprocessable Content", 429: "Too Many Requests", 503: "Service Unavailable",
}


class Problem(Exception):
    """À lever dans vos routes : raise Problem(409, "not-ready", "sbx-… n'est pas prête")."""

    def __init__(self, status: int, slug: str, detail: str = "", headers: dict | None = None):
        self.status, self.slug, self.detail, self.headers = status, slug, detail, headers or {}


def problem_response(request: Request, status: int, slug: str, detail: str = "", headers: dict | None = None) -> JSONResponse:
    body = {"type": f"/errors/{slug}", "title": TITLES.get(status, "Error"), "status": status, "instance": request.url.path}
    if detail:
        body["detail"] = detail
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers=headers)


def install(app) -> None:
    """Branche les gestionnaires d'erreurs sur l'application FastAPI."""

    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem):
        return problem_response(request, exc.status, exc.slug, exc.detail, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(x) for x in first.get("loc", []))
        return problem_response(request, 422, "validation", f"{where} : {first.get('msg', 'invalide')}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        slug = {404: "not-found", 405: "method-not-allowed"}.get(exc.status_code, "http")
        headers = getattr(exc, "headers", None)
        if exc.status_code == 405:  # Allow doit lister toutes les méthodes de la ressource (RFC 9110)
            methods = set()
            for route in request.app.router.routes:
                match, _ = route.matches(request.scope)
                if match != Match.NONE and getattr(route, "methods", None):
                    methods |= route.methods
            headers = {"Allow": ", ".join(sorted(methods - {"HEAD"}))}
        return problem_response(request, exc.status_code, slug, str(exc.detail or ""), headers)
