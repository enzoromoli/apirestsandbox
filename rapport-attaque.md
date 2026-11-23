# Rapport d'attaque — sandboxd

Essais contre le serveur (`SANDBOXD_API_KEY=dev-key`) et de vrais conteneurs.
`AG` est un jeton d'agent de la sandbox A, émis par `POST /v1/sandboxes/A/tokens`.

| # | Attaque | Résultat | Bloqué par |
|---|---------|----------|------------|
| 1 | `curl /v1/sandboxes` sans en-tête | 401 + `WWW-Authenticate: Bearer` | `current_actor` |
| 2 | `Authorization: Bearer mauvaise-cle` | 401 | comparaison de la clé |
| 3 | Jeton forgé (`alg: none`, autre secret) | 401 | `jwt.decode(..., algorithms=["HS256"])` |
| 4 | Jeton expiré | 401 « jeton expiré » | claim `exp` |
| 5 | `AG` sur la sandbox B (GET, exec, fichiers) | 404, comme une sandbox inexistante | `sandbox_access` |
| 6 | `AG` liste, crée, modifie, détruit, émet un jeton | 403 | `operator_only` |
| 7 | `path=../etc/passwd`, `/etc/passwd`, `a/../../x` | 422 | `check_path` |
| 8 | Exec `wget http://1.1.1.1/` | `Network unreachable` | `NetworkMode: none` |
| 9 | Exec `id`, `su -c id root` | `uid=1000`, `su` refusé | `User`, `CapDrop: ALL`, `no-new-privileges` |
| 10 | Exec `echo x > /etc/evil` | `Read-only file system` | `ReadonlyRootfs` |
| 11 | Exec qui lance 300 `sleep &` | `Cannot fork` | `PidsLimit: 128` |
| 12 | Exec `sleep 30` avec `timeout_seconds: 2` | `timed_out: true` en 2 s | `timeout -s KILL` |
| 13 | `POST /v1/sandboxes` avec `ubuntu:latest` | 422 | liste blanche d'images |

Limite connue : un agent peut créer par exec un lien symbolique vers un dossier
(`ln -s /etc d`), puis lire `GET /files?path=d/shadow`. L'API archive de Docker suit
le lien et lit en root : cette lecture n'est pas bloquée.
