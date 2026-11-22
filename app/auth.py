"""Authentification : clé d'API de l'opérateur et jetons JWT des agents."""
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Request

from .errors import Problem

API_KEY = os.environ.get("SANDBOXD_API_KEY", "")
if not API_KEY:
    raise SystemExit("sandboxd : la variable d'environnement SANDBOXD_API_KEY est obligatoire (clé de l'opérateur).")

# Sans secret fixé, les jetons émis ne survivent pas à un redémarrage.
JWT_SECRET = os.environ.get("SANDBOXD_JWT_SECRET") or secrets.token_urlsafe(32)
TOKEN_TTL = timedelta(minutes=15)


def issue_token(sandbox_id: str) -> tuple[str, datetime]:
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = issued_at + TOKEN_TTL
    claims = {"sub": sandbox_id, "role": "agent", "iat": issued_at, "exp": expires_at}
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256"), expires_at


def unauthorized(detail: str) -> Problem:
    return Problem(401, "unauthorized", detail, {"WWW-Authenticate": "Bearer"})


def current_actor(request: Request) -> dict:
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    credentials = credentials.strip()
    if scheme.lower() != "bearer" or not credentials:
        raise unauthorized("en-tête Authorization: Bearer manquant")
    if hmac.compare_digest(credentials.encode(), API_KEY.encode()):
        request.state.actor = {"role": "operator"}
        return request.state.actor
    try:
        claims = jwt.decode(credentials, JWT_SECRET, algorithms=["HS256"],
                            options={"require": ["sub", "role", "exp"]})
    except jwt.ExpiredSignatureError:
        raise unauthorized("jeton expiré")
    except jwt.InvalidTokenError:
        raise unauthorized("clé ou jeton invalide")
    if claims["role"] != "agent":
        raise unauthorized("clé ou jeton invalide")
    request.state.actor = {"role": "agent", "sandbox_id": claims["sub"]}
    return request.state.actor


def operator_only(actor: Annotated[dict, Depends(current_actor)]) -> dict:
    if actor["role"] != "operator":
        raise Problem(403, "forbidden", "réservé à l'opérateur")
    return actor


def sandbox_access(sandbox_id: str, actor: Annotated[dict, Depends(current_actor)]) -> dict:
    # Un agent qui vise une autre sandbox reçoit 404 : on ne révèle pas qu'elle existe.
    if actor["role"] == "agent" and actor["sandbox_id"] != sandbox_id:
        raise Problem(404, "not-found", f"{sandbox_id} n'existe pas")
    return actor


Operator = Annotated[dict, Depends(operator_only)]
OperatorOrAgent = Annotated[dict, Depends(sandbox_access)]
