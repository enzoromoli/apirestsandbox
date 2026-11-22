"""sbx — le client en ligne de commande de sandboxd (TP4).

    python -m client.sbx ls [--status ready]
    python -m client.sbx create --image alpine:3.20 [--wait]
    python -m client.sbx exec [--timeout 30] sbx-a1b2c3d4 -- ls -la
    python -m client.sbx rm sbx-a1b2c3d4

Options globales, avant la commande : -v (nouveaux essais et compteur sur
stderr), --json (sortie lisible par un autre script).

L'adresse de l'API vient de SANDBOXD_URL (par défaut http://localhost:8000).
Le client tient face à une API capricieuse : timeout sur chaque appel, nouveaux
essais sur 429, 502, 503, 504 et erreurs réseau (seulement pour une requête
idempotente ou qui porte une Idempotency-Key), Retry-After respecté, sinon
backoff exponentiel avec jitter, abandon clair après MAX_ATTEMPTS essais.
"""
import argparse
import email.utils
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx

API = os.environ.get("SANDBOXD_URL", "http://localhost:8000")

TIMEOUT = httpx.Timeout(3.0, connect=2.0)         # une réponse lente (plus de 3 s) est abandonnée puis rejouée
DELETE_TIMEOUT = httpx.Timeout(15.0, connect=2.0)  # docker rm -f peut prendre quelques secondes
MAX_ATTEMPTS = 8                                  # 1 essai + 7 nouveaux essais, puis abandon
RETRY_STATUSES = {429, 502, 503, 504}
RETRY_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}
BACKOFF_BASE, BACKOFF_CAP = 0.5, 8.0              # secondes : 0.5, 1, 2, 4, 8, 8…
MAX_RETRY_AFTER = 30.0                            # au-delà, on abandonne plutôt que de rester bloqué
WAIT_TIMEOUT = 120.0                              # create --wait : délai maximal avant ready

VERBOSE = False
STATS = {"calls": 0, "retries": 0}


class ApiError(Exception):
    """Erreur définitive : inutile de réessayer."""


def note(message: str) -> None:
    if VERBOSE:
        print(f"sbx: {message}", file=sys.stderr)


def describe(r: httpx.Response) -> str:
    """« 404 sbx-… n'existe pas » : le statut et le detail du problem+json."""
    try:
        body = r.json()
    except ValueError:
        body = None
    detail = (body.get("detail") or body.get("title")) if isinstance(body, dict) else None
    return f"{r.status_code} {detail or r.reason_phrase}"


def retry_after(r: httpx.Response) -> float | None:
    """Retry-After en secondes, qu'il soit donné en secondes ou en date HTTP."""
    value = r.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def backoff(attempt: int) -> float:
    """Backoff exponentiel avec jitter complet : un tirage entre 0 et 0.5 × 2^(n-1), plafonné."""
    return random.uniform(0, min(BACKOFF_CAP, BACKOFF_BASE * 2 ** (attempt - 1)))


def request(client: httpx.Client, method: str, path: str, *, allow: tuple[int, ...] = (), **kwargs) -> httpx.Response:
    """Envoie une requête et renvoie la réponse finale (2xx, ou un statut listé dans allow).

    Rejoue 429, 502, 503, 504 et les erreurs réseau, seulement si la requête est
    idempotente ou porte une Idempotency-Key : un POST sans clé ne se rejoue pas.
    Lève ApiError pour une erreur définitive ou après MAX_ATTEMPTS essais.
    """
    method = method.upper()
    kwargs.setdefault("timeout", TIMEOUT)
    headers = kwargs.get("headers") or {}
    replayable = method in IDEMPOTENT_METHODS or any(h.lower() == "idempotency-key" for h in headers)
    what = f"{method} {path}"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        STATS["calls"] += 1
        try:
            r = client.request(method, path, **kwargs)
        except RETRY_ERRORS as exc:
            reason = f"{type(exc).__name__} ({exc})" if str(exc) else type(exc).__name__
            if not replayable:
                raise ApiError(f"{what} : {reason} ; non rejoué ({method} sans Idempotency-Key), "
                               "l'action a peut-être eu lieu") from exc
            if attempt == MAX_ATTEMPTS:
                raise ApiError(f"{what} : abandon après {attempt} essais, dernier échec : {reason}") from exc
            delay = backoff(attempt)
        except httpx.HTTPError as exc:  # URL invalide, protocole inconnu… : rejouer ne changerait rien
            raise ApiError(f"{what} : {exc}") from exc
        else:
            if r.status_code not in RETRY_STATUSES:
                if r.status_code >= 400 and r.status_code not in allow:
                    raise ApiError(f"{what} : {describe(r)}")
                return r
            reason = describe(r)
            if not replayable:
                raise ApiError(f"{what} : {reason} ; non rejoué ({method} sans Idempotency-Key)")
            if attempt == MAX_ATTEMPTS:
                raise ApiError(f"{what} : abandon après {attempt} essais, dernier échec : {reason}")
            delay = retry_after(r)
            if delay is None:
                delay = backoff(attempt)
            elif delay > MAX_RETRY_AFTER:
                raise ApiError(f"{what} : {reason}, le serveur demande d'attendre {delay:.0f} s : abandon")
        STATS["retries"] += 1
        note(f"{what} : {reason}, nouvel essai dans {delay:.1f} s ({attempt}/{MAX_ATTEMPTS})")
        time.sleep(delay)
    raise AssertionError("inatteignable")


def payload(r: httpx.Response):
    try:
        return r.json()
    except ValueError:
        raise ApiError(f"réponse illisible ({r.status_code}, {r.headers.get('content-type', '?')})") from None


def emit(args, data, text: str | None = None) -> None:
    if args.json:
        print(json.dumps(data, ensure_ascii=False))
    elif text is not None:
        print(text)


def cmd_ls(client: httpx.Client, args) -> None:
    """Suit next_page_token jusqu'au bout, puis affiche une ligne par sandbox."""
    params = {"page_size": 100}
    if args.status:
        params["status"] = args.status
    sandboxes, seen_ids, seen_tokens = [], set(), set()
    while True:
        page = payload(request(client, "GET", "/v1/sandboxes", params=params))
        for sb in page["items"]:
            if sb["id"] not in seen_ids:  # garde-fou si le serveur pagine par décalage
                seen_ids.add(sb["id"])
                sandboxes.append(sb)
        token = page.get("next_page_token")
        if not token:
            break
        if token in seen_tokens:
            raise ApiError(f"pagination : jeton {token!r} déjà vu, arrêt pour ne pas boucler")
        seen_tokens.add(token)
        params["page_token"] = token
    if args.json:
        emit(args, sandboxes)
    else:
        for sb in sandboxes:
            print(f'{sb["id"]}\t{sb["status"]}\t{sb["image"]}')


def wait_ready(client: httpx.Client, location: str) -> dict:
    """Interroge Location jusqu'à ready (renvoie la sandbox) ou failed/terminated (ApiError)."""
    deadline = time.monotonic() + WAIT_TIMEOUT
    delay = 0.5
    while True:
        sb = payload(request(client, "GET", location))
        if sb["status"] == "ready":
            return sb
        if sb["status"] in ("failed", "terminated"):
            raise ApiError(f"{sb['id']} est passée en {sb['status']}")
        if time.monotonic() + delay > deadline:
            raise ApiError(f"{sb['id']} toujours {sb['status']} après {WAIT_TIMEOUT:.0f} s")
        note(f"{sb['id']} : {sb['status']}, nouvelle lecture dans {delay:.1f} s")
        time.sleep(delay)
        delay = min(delay * 1.5, 3.0)


def cmd_create(client: httpx.Client, args) -> None:
    """Création rejouable : une Idempotency-Key par création, la même à chaque nouvel essai."""
    key = str(uuid.uuid4())
    r = request(client, "POST", "/v1/sandboxes", json={"image": args.image}, headers={"Idempotency-Key": key})
    sb = payload(r)
    if args.wait:
        sb = wait_ready(client, r.headers.get("Location") or f"/v1/sandboxes/{sb['id']}")
    emit(args, sb, sb["id"])


def cmd_exec(client: httpx.Client, args) -> int:
    """Affiche stdout et stderr séparément, et sort avec le code de la commande (124 si tuée par le délai)."""
    body = {"cmd": args.cmd}
    if args.timeout:
        body["timeout_seconds"] = args.timeout
    read = (args.timeout or 30) + 10  # le serveur attend la fin de la commande
    r = request(client, "POST", f"/v1/sandboxes/{args.id}/exec", json=body, timeout=httpx.Timeout(read, connect=2.0))
    res = payload(r)
    if args.json:
        emit(args, res)
    else:
        sys.stdout.write(res["stdout"])
        sys.stdout.flush()
        sys.stderr.write(res["stderr"])
    if res.get("truncated"):
        print("sbx: sortie tronquée à 1 Mio", file=sys.stderr)
    if res.get("timed_out") or res.get("exit_code") is None:
        print(f"sbx: commande tuée après {args.timeout or 30} s", file=sys.stderr)
        return 124
    return res["exit_code"]


def cmd_rm(client: httpx.Client, args) -> None:
    """DELETE est idempotent : un 404 veut dire « déjà supprimée », ce n'est pas une erreur."""
    r = request(client, "DELETE", f"/v1/sandboxes/{args.id}", allow=(404,), timeout=DELETE_TIMEOUT)
    gone = r.status_code == 404
    if gone and not args.json:
        print(f"sbx: {args.id} n'existe pas (déjà supprimée)", file=sys.stderr)
    emit(args, {"id": args.id, "deleted": not gone})


def main() -> int:
    global VERBOSE
    parser = argparse.ArgumentParser(prog="sbx")
    parser.add_argument("-v", "--verbose", action="store_true", help="nouveaux essais et compteur sur stderr")
    parser.add_argument("--json", action="store_true", help="sortie JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ls"); p.add_argument("--status"); p.set_defaults(func=cmd_ls)
    p = sub.add_parser("create"); p.add_argument("--image", required=True); p.add_argument("--wait", action="store_true"); p.set_defaults(func=cmd_create)
    p = sub.add_parser("exec"); p.add_argument("--timeout", type=int); p.add_argument("id"); p.add_argument("cmd", nargs=argparse.REMAINDER); p.set_defaults(func=cmd_exec)
    p = sub.add_parser("rm"); p.add_argument("id"); p.set_defaults(func=cmd_rm)
    args = parser.parse_args()
    if getattr(args, "cmd", None) and args.cmd[:1] == ["--"]:
        args.cmd = args.cmd[1:]
    VERBOSE = args.verbose
    t0 = time.monotonic()
    with httpx.Client(base_url=API, timeout=TIMEOUT) as client:  # un seul client : connexions réutilisées
        try:
            return args.func(client, args) or 0
        except ApiError as exc:
            print(f"sbx: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 130
        finally:
            note(f"appels {STATS['calls']}, nouveaux essais {STATS['retries']}, durée {time.monotonic() - t0:.1f} s")


if __name__ == "__main__":
    sys.exit(main())
