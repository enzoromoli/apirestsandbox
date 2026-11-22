# TP4 — sbx, un client robuste

Mesures faites contre l'API capricieuse (`make flaky`, port 8001), avec `SANDBOXD_URL=http://localhost:8001`.
Le serveur est relancé avant chaque série, pour repartir de 500 sandboxes. Les durées comptent environ 1,5 s
de démarrage de Python par commande (WSL, dépôt sur `/mnt/c`).

## 1. Constat de départ : le squelette naïf

```bash
FLAKY_SEED=42 make flaky
.venv/bin/python -m client.sbx ls | wc -l
for i in $(seq 10); do .venv/bin/python -m client.sbx create --image alpine:3.20; done
curl -s localhost:8001/_stats
```

| Mesure | Résultat |
| --- | --- |
| `sbx ls \| wc -l` | **20** lignes, pour 500 sandboxes |
| 10 × `sbx create` | **7** identifiants affichés, **3** plantages (`KeyError: 'id'`, trace Python) |
| Sandboxes en plus dans `/_stats` | **+8** (`created: 8`) : une sandbox existe alors que le client a affiché une erreur |
| `/_stats` après | `requests 11, fail_429 1, fail_503 1, slow 1, lost 1, created 8` |

## 2. Ce qui échouait, et pourquoi

| Symptôme | Cause |
| --- | --- |
| `ls` n'affiche que 20 lignes | `next_page_token` est ignoré : seule la première page est lue. |
| `create` plante sur un 429 ou un 503 | Aucun nouvel essai, `Retry-After` ignoré. Le client lit `["id"]` dans un problem+json, d'où `KeyError` et une trace Python. |
| +8 sandboxes pour 7 succès | Réponse perdue (502) : la sandbox est créée, mais le client croit à un échec. Comme le POST n'a pas d'`Idempotency-Key`, le rejouer créerait un doublon. |
| Lenteur | Aucun timeout choisi : seul le délai par défaut de httpx (5 s) bornait l'attente. |
| `rm` sort 0 même sur un 429 ou un 503 | Le statut n'est jamais vérifié : la sandbox n'est pas supprimée, et aucun message ne le dit. |
| `exec` | Affiche le JSON brut et sort toujours avec le code 0, quel que soit le code de la commande. |

## 3. Ce que fait le client (`client/sbx.py`)

Tout passe par `request()`, avec un seul `httpx.Client` par commande.

| Point du sujet | Choix |
| --- | --- |
| Timeouts | 3 s en lecture et 2 s en connexion par défaut (la lenteur de l'API capricieuse dure 4 s). 15 s pour `DELETE` (le serveur lance `docker rm -f`). Pour `exec` : `timeout_seconds` + 10 s. |
| Retries | Sur 429, 502, 503, 504, timeout et erreur réseau. Seulement pour GET, PUT, DELETE, ou pour une requête qui porte une `Idempotency-Key`. Jamais sur 400, 404, 409 ou 422. |
| Attente | `Retry-After` respecté, en secondes ou en date HTTP. Au-delà de 30 s, abandon immédiat. Sinon, backoff exponentiel à jitter complet : tirage entre 0 et 0,5 × 2^(n-1) s, plafonné à 8 s. |
| Abandon | Au bout de 8 essais : message `sbx: … abandon après 8 essais, dernier échec : …` et code de sortie 1. |
| Création rejouable | Une `Idempotency-Key` (uuid4) par `create`, renvoyée telle quelle à chaque nouvel essai, avec le même corps. |
| Pagination | `ls` demande `page_size=100` et suit `next_page_token` jusqu'à `null`. Il écarte un identifiant déjà vu et s'arrête si un jeton revient. Rien n'est affiché avant la dernière page : soit la liste complète, soit une erreur. |
| `--wait` | Interroge l'URL de `Location` toutes les 0,5 s, puis jusqu'à toutes les 3 s, pendant 120 s au plus. `ready` : affiche l'identifiant. `failed` ou `terminated` : erreur, code 1. |
| `exec` | stdout sur stdout, stderr sur stderr. Code de sortie = celui de la commande, 124 si elle a été tuée par le délai. |
| `rm` | Un 404 veut dire « déjà supprimée » : code 0, avec une note sur stderr. |
| Bonus | `-v` affiche chaque nouvel essai, puis un compteur : appels, nouveaux essais, durée. `--json` produit une sortie JSON. Le disjoncteur n'est pas fait. |

Pourquoi 8 essais : sur `create`, un essai échoue avec une probabilité d'environ 0,2 (429/503) + 0,1 (lenteur) + 0,7 × 0,15
(réponse perdue) ≈ 0,4. Avec 5 essais, une création abandonne dans 1 % des cas, soit environ 20 % de risque sur 20 créations.
Avec 8 essais, c'est 0,07 % par création, soit environ 1,4 % sur 20.

## 4. Ce qui tient maintenant : les mêmes mesures

```bash
.venv/bin/python -m client.sbx -v ls | wc -l
for i in $(seq 10); do .venv/bin/python -m client.sbx -v create --image alpine:3.20; done
curl -s localhost:8001/_stats
```

| Mesure | Naïf (graine 42) | sbx (graine 42) | sbx (sans graine) |
| --- | --- | --- | --- |
| `ls \| wc -l` | 20 | **500** | **500** |
| Doublons (`sort \| uniq -d`) | 0 | 0 | 0 |
| Coût de `ls` | 1 appel, 1,8 s | 33 appels, 8 nouveaux essais, 18,4 s | 34 appels, 9 nouveaux essais, 23,5 s |
| 10 × `create` | 7 succès, 3 plantages | **10 succès** | **10 succès** |
| Sandboxes en plus | +8 | **+10** | **+10** |
| Coût des 10 `create` | 22 s | 20 appels, 10 nouveaux essais, 39 s | 22 appels, 12 nouveaux essais, 34 s |

Les vérifications du sujet, dans la même session :

| Vérification | sbx (graine 42) | sbx (sans graine) |
| --- | --- | --- |
| 20 × `create` | 20 succès, **+20** sandboxes (27 appels, 49 s) | 20 succès, **+20** sandboxes (30 appels, 58 s) |
| Réponses perdues / rejeux par clé (`/_stats`) | `lost 2`, `idempotent_replays 2` | `lost 3`, `idempotent_replays 3` |
| `create --wait` | identifiant affiché, sandbox `ready` (9,2 s) | identifiant affiché, sandbox `ready` (8,0 s) |
| `rm` deux fois de suite | code 0, puis code 0 | code 0, puis code 0 |
| `ls` final | 530 lignes = 530 dans `/_stats`, 0 doublon | 530 lignes = 530 dans `/_stats`, 0 doublon |
| API éteinte (port fermé) | 8 essais puis `abandon après 8 essais : ConnectError`, code 1, 17 s | — |

Chaque réponse perdue a été rattrapée par un rejeu avec la même clé : autant de sandboxes en plus que de succès.

## 5. Contre notre sandboxd (`SANDBOXD_URL=http://localhost:8000`)

Avec Docker (images `alpine:3.20` et `python:3.12-slim` déjà téléchargées) :

| Commande | Résultat |
| --- | --- |
| `create --wait` (alpine, python) | identifiant affiché une fois `ready`, en 3,2 s et 3,5 s, code 0 |
| `exec … -- echo bonjour` | `bonjour`, code 0 |
| `exec … -- sh -c 'echo SUR_STDOUT; echo SUR_STDERR >&2'` | `SUR_STDOUT` sur stdout seulement, `SUR_STDERR` sur stderr seulement |
| `exec … -- sh -c 'exit 3'` | code de sortie 3 |
| `exec … -- python -c 'print(2 + 2)'` | `4`, code 0 |
| `exec --timeout 2 … -- sleep 5` | `sbx: commande tuée après 2 s`, code 124, au bout de 4 s |
| `create --image ubuntu:latest` | `422 image : Input should be …`, code 1, sans nouvel essai |
| `ls`, `ls --status ready`, `ls --json` | 8 sandboxes, 0 doublon ; 5 `ready` ; 8 en JSON |
| `rm` deux fois sur chacune des 8 | code 0 puis code 0 ; ensuite `ls` est vide et aucun conteneur n'est encore en marche |

Sans Docker, `exec` sur une sandbox `pending` donne `409 … n'est pas prête` (code 1). `create --wait` abandonne au bout de
120 s (code 1), sans rester bloqué, parce que la sandbox ne quitte jamais `pending`.

Deux points côté serveur, à voir avec Enzo :

- `provision()` n'attrape que `DockerError`. Quand Docker est absent, `httpx.ConnectError` tue le thread et la sandbox reste
  `pending` au lieu de passer en `failed`. Correction : `except (docker.DockerError, httpx.HTTPError)`.
- L'`Idempotency-Key` n'est pas encore gérée par le serveur (tâche E2). D'ici là, une réponse perdue peut créer un doublon
  contre notre sandboxd. Le client envoie déjà la clé.

## 6. Limites connues

- `exec` n'est jamais rejoué : c'est un POST, et le contrat ne prévoit pas d'`Idempotency-Key` pour lui. Contre l'API
  capricieuse, 20 `exec` (graine 42) donnent **16 succès et 4 refus clairs** (1 × 429, 3 × 503 : « non rejoué, POST sans
  Idempotency-Key »).
- Quand sbx lui-même échoue, il sort avec le code 1, qui peut se confondre avec le code 1 d'une commande lancée par `exec`.
  Le message `sbx: …` sur stderr permet de les distinguer.
