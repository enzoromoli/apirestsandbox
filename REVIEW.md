# Problèmes de l'autre binôme
## Problème 1: path n'interdit ni "../" ni les chemins absolus
FilePath est seulement décrit comme "relatif à /workspace" (minLength: 1, aucun "pattern").
Rien n'empêche "../../etc/passwd", "/etc/passwd" ou un symlink qui sort de "/workspace", et le
code de refus n'est pas précisé. Le cas d'un chemin qui désigne un dossier, ou d'un "PUT" dont le
dossier parent n'existe pas, n'est pas défini non plus.

## Problème 2: 404 ambigu entre sandbox absente et fichier absent
Sur "readFile" / "writeFile", la réponse "NotFound" est décrite "Sandbox introuvable" alors
qu'elle sert aussi pour un fichier absent. Les "type" de Problem ne sont pas définis, donc un
client ne peut pas savoir lequel des deux manque. Même souci pour les deux 409 : conflit
d'Idempotency-Key et sandbox pas prête.

## Problème 3: frontière 400 / 422 non définie
La plupart des opérations listent à la fois 400 et 422 sans dire lequel s'applique. Par exemple,
"page_size=0", "status=foo" ou un "ttl_seconds" hors bornes peuvent donner l'un ou l'autre. Deux
équipes coderaient donc des comportements différents à partir du même contrat.
