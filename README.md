# sandboxd — starter kit

Point de départ du projet fil rouge. Sujets : distribués en cours (projet sandboxd, TP du 28/10).

## Prérequis

- Node 18 ou plus (pour `npx` : Spectral, Prism, Redocly)
- Python 3.11 ou plus
- Docker, et l'accès à son socket

## Démarrer

```bash
make lint      # le contrat est valide
make install   # dépendances Python dans .venv
make run       # sandboxd sur http://localhost:8000
curl localhost:8000/healthz
```

**macOS (Docker Desktop, OrbStack) :** le socket n'est pas toujours dans `/var/run/docker.sock`. Trouvez-le, puis passez-le à `make run` :

```bash
docker context inspect --format '{{.Endpoints.docker.Host}}'
make run DOCKER_SOCKET=$HOME/.orbstack/run/docker.sock
```

**Avant le TP4**, téléchargez les images une fois (sinon la première création est lente) :

```bash
docker pull python:3.12-slim && docker pull node:22-slim && docker pull alpine:3.20
```

## Commandes

| Commande | Rôle |
|---|---|
| `make lint` | Vérifie le contrat avec Spectral et les règles du cours (`.spectral.yaml`) |
| `make mock` | Simule l'API à partir du contrat, avec Prism, sur le port 4010 |
| `make docs` | Génère la documentation HTML du contrat (`docs.html`) |
| `make run` | Lance sandboxd, rechargé à chaque modification |
| `make test-contract` | Rejoue le contrat contre sandboxd, avec Schemathesis (sandboxd doit tourner) |
| `make clean` | Supprime les conteneurs créés par sandboxd |

## Ce qui est fourni

| Fichier | Contenu |
|---|---|
| `openapi.yaml` | Le squelette du contrat : schémas de base, une opération d'exemple |
| `.spectral.yaml` | Les règles du cours : `/v1`, erreurs en problem+json, au moins une 4xx par opération, snake_case |
| `app/docker.py` | Le client de l'API Docker Engine : créer, exécuter, lire et écrire des fichiers, supprimer |
| `app/errors.py` | Les erreurs au format problem+json : `raise Problem(409, "not-ready", "…")` |
| `app/main.py` | Le squelette de l'API : stockage en mémoire, création en tâche de fond, `getSandbox` d'exemple |

Le contrat fait foi : FastAPI ne publie pas sa propre documentation.
