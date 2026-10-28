# TP2

## 1. 
```bash
curl -i -X POST localhost:4010/v1/sandboxes \
     -H 'Content-Type: application/json' -d '{"image": "python:3.12-slim"}'
```
```bash
[2:58:45 PM] › [HTTP SERVER] post /v1/sandboxes ℹ  info      Request received
[2:58:45 PM] ›     [NEGOTIATOR] ℹ  info      Request contains an accept header: */*
[2:58:45 PM] ›     [VALIDATOR] ✔  success   The request passed the validation rules. Looking for the best response
[2:58:45 PM] ›     [NEGOTIATOR] ✔  success   Found a compatible content for */*
[2:58:45 PM] ›     [NEGOTIATOR] ✔  success   Responding with the requested status code 202
[2:58:45 PM] ›     [NEGOTIATOR] ℹ  info      > Responding with "202"
```

```bash
HTTP/1.1 202 Accepted
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: *
Location: ../dictionary
Content-type: application/json
Content-Length: 193
Date: Wed, 28 Oct 2026 13:58:45 GMT
Connection: keep-alive
Keep-Alive: timeout=5

{"id":"sbx-a1b2c3d4","image":"python:3.12-slim","status":"pending","ttl_seconds":600,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T14:00:00Z","expires_at":"2026-10-28T14:10:00Z"}
```

# Création acceptée : quel code, quel Location ?

Code **202 Accepted** : la création est asynchrone, la sandbox est renvoyée en état pending. Prism affiche `../dictionary` dans Location.


## 2.
```bash
curl -i -X POST localhost:4010/v1/sandboxes \
     -H 'Content-Type: application/json' -d '{"image": "ubuntu"}'
```
```bash
[2:59:04 PM] › [HTTP SERVER] post /v1/sandboxes ℹ  info      Request received
[2:59:04 PM] ›     [NEGOTIATOR] ℹ  info      Request contains an accept header: */*
[2:59:04 PM] ›     [VALIDATOR] ⚠  warning   Request did not pass the validation rules
[2:59:04 PM] ›     [VALIDATOR] ✖  error     Request body property image must be equal to one of the allowed values: python:3.12-slim, node:22-slim, alpine:3.20
[2:59:04 PM] ›     [NEGOTIATOR] ✔  success   Found response 422. I'll try with it.
[2:59:04 PM] ›     [NEGOTIATOR] ✔  success   The response 422 has a schema. I'll keep going with this one
[2:59:04 PM] ›     [NEGOTIATOR] ✔  success   Responding with the requested status code 422
[2:59:04 PM] ›     [NEGOTIATOR] ℹ  info      > Responding with "422"
[2:59:04 PM] ›     [VALIDATOR] ✖  error     Violation: request.body.image Request body property image must be equal to one of the allowed values: python:3.12-slim, node:22-slim, alpine:3.20
```

```bash
HTTP/1.1 422 Unprocessable Entity
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: *
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: *
sl-violations: [{"location":["request","body","image"],"severity":"Error","code":"enum","message":"Request body property image must be equal to one of the allowed values: python:3.12-slim, node:22-slim, alpine:3.20"}]
Content-type: application/problem+json
Content-Length: 150
Date: Wed, 28 Oct 2026 13:59:04 GMT
Connection: keep-alive
Keep-Alive: timeout=5

{"type":"/problems/not-found","title":"Sandbox introuvable","status":404,"detail":"sbx-a1b2c3d4 n'existe pas","instance":"/v1/sandboxes/sbx-a1b2c3d4"}
```

# Image interdite : quel code ?

Code **422 Unprocessable Entity**, en `application/problem+json` : `ubuntu` n'est pas dans la liste des images.


## 3.
```bash
curl -s -X POST localhost:4010/v1/sandboxes/sbx-a1b2c3d4/exec \
     -H 'Content-Type: application/json' -d '{"cmd": ["ls"]}'
```

```bash
[2:59:57 PM] › [HTTP SERVER] post /v1/sandboxes/sbx-a1b2c3d4/exec ℹ  info      Request received
[2:59:57 PM] ›     [NEGOTIATOR] ℹ  info      Request contains an accept header: */*
[2:59:57 PM] ›     [VALIDATOR] ✔  success   The request passed the validation rules. Looking for the best response
[2:59:57 PM] ›     [NEGOTIATOR] ✔  success   Found a compatible content for */*
[2:59:57 PM] ›     [NEGOTIATOR] ✔  success   Responding with the requested status code 200
[2:59:57 PM] ›     [NEGOTIATOR] ℹ  info      > Responding with "200"
```

```bash
{"exit_code":0,"stdout":"4\n","stderr":"","duration_ms":42,"timed_out":false,"truncated":false}
```

# Exécution : la réponse ressemble-t-elle à ce que vous attendez ?

Oui pour la forme : code 200 et les six champs attendus (exit_code, stdout, stderr, duration_ms, timed_out, truncated). Le contenu ne correspond pas à ls, car Prism n'exécute rien et renvoie toujours l'exemple de ExecResult.
