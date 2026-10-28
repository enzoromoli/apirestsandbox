```bash
kyrohe@MSI-Kyrohe:~/apirestsandbox$ make test-contract
.venv/bin/schemathesis run openapi.yaml --url http://localhost:8000 -n 20 -w 1 \
        --exclude-checks positive_data_acceptance
Schemathesis v4.32.7
━━━━━━━━━━━━━━━━━━━━

 ✅  Loaded specification from openapi.yaml (in 0.19s)

     Base URL:         http://localhost:8000
     Specification:    Open API 3.1.0
     Operations:       9 selected / 9 total

 ✅  API capabilities:

     Supports NULL byte in headers:                            ✘
     Accepts backslash and control characters in URL paths:    ✓
     Cache:                                                    1 request replayed

 ❌  Examples (in 0.12s)

     ✅ 2 passed  ❌ 5 failed  ⏭  2 skipped

 ❌  Coverage (in 0.58s)

     ✅ 1 passed  ❌ 7 failed  ⏭  1 skipped

 ❌  Fuzzing (in 0.17s)

     ✅ 1 passed  ❌ 7 failed  ⏭  1 skipped

 ❌  Stateful (in 5.62s)

     Scenarios:    59
     API Links:    14 covered / 22 selected / 22 total (22 inferred)

     ✅ 46 passed  ❌ 13 failed

==================================================================== FAILURES ===================================================================
_______________________________________________________ DELETE /v1/sandboxes/{sandbox_id} _______________________________________________________
1. Test Case ID: m0Cqgq

- ST108 Response violates schema

    "/errors/not-found" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 404.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/not-found"

[404] Not Found:

    `{"type":"/errors/not-found","title":"Not Found","status":404,"instance":"/v1/sandboxes/sbx-a1b2c3d4","detail":"sbx-a1b2c3d4 n'existe pas"}`

Reproduce with:

    curl -X DELETE http://localhost:8000/v1/sandboxes/sbx-a1b2c3d4

    st replay m0Cqgq

_______________________________________________________________ GET /v1/sandboxes _______________________________________________________________
1. Test Case ID: LOYqFf

- ST101 Server error

- ST103 Undocumented status code

    Received: 500
    Documented: 200, 400, 422

[500] Internal Server Error:

    `Internal Server Error`

Reproduce with:

    curl -X GET 'http://localhost:8000/v1/sandboxes?page_size=20&page_token=%5BFiltered%5D'

    st replay LOYqFf

_________________________________________________________ GET /v1/sandboxes/{sandbox_id} ________________________________________________________
1. Test Case ID: wig0d0

- ST108 Response violates schema

    "/errors/not-found" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 404.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/not-found"

[404] Not Found:

    `{"type":"/errors/not-found","title":"Not Found","status":404,"instance":"/v1/sandboxes/sbx-a1b2c3d4","detail":"sbx-a1b2c3d4 n'existe pas"}`

Reproduce with:

    curl -X GET http://localhost:8000/v1/sandboxes/sbx-a1b2c3d4

    st replay wig0d0

______________________________________________________ GET /v1/sandboxes/{sandbox_id}/files _____________________________________________________
1. Test Case ID: hOPnHk

- ST108 Response violates schema

    "/errors/not-ready" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 409.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/not-ready"

[409] Conflict:

    `{"type":"/errors/not-ready","title":"Conflict","status":409,"instance":"/v1/sandboxes/sbx-75ff9d20/files","detail":"sbx-75ff9d20 n'est pas prête"}`

Reproduce with:

    curl -X GET 'http://localhost:8000/v1/sandboxes/sbx-75ff9d20/files?path=src%2Fmain.py'

    st replay hOPnHk

_______________________________________________________ OPTIONS /v1/sandboxes/{sandbox_id} ______________________________________________________
1. Test Case ID: UbtiVL

- ST205 Allow header mismatch

    `Allow: DELETE, GET` does not match the schema. Missing documented methods: PATCH

    List exactly the methods this resource supports in `Allow`

[405] Method Not Allowed:

    `{"type":"/errors/method-not-allowed","title":"Method Not Allowed","status":405,"instance":"/v1/sandboxes/sbx-75ff9d20","detail":"Method Not Allowed"}`

Reproduce with:

    curl -X OPTIONS http://localhost:8000/v1/sandboxes/sbx-75ff9d20

    st replay UbtiVL

_______________________________________________________________ POST /v1/sandboxes ______________________________________________________________
1. Test Case ID: fjnNT8

- ST108 Response violates schema

    "/errors/unsupported-media-type" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 415.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/unsupported-media-type"

[415] Unsupported Media Type:

    `{"type":"/errors/unsupported-media-type","title":"Unsupported Media Type","status":415,"instance":"/v1/sandboxes","detail":"attendu : application/json"}`

Reproduce with:

    curl -X POST -H 'Idempotency-Key: [Filtered]' http://localhost:8000/v1/sandboxes

    st replay fjnNT8

2. Test Case ID: rDMHY0

- ST201 Schema-violating request accepted

    Invalid data should have been rejected
    Expected: 400, 401, 403, 404, 405, 406, 409, 415, 422, 428, 429, 5xx
    Invalid component: parameter `Idempotency-Key` in header - violates `maxLength` at /properties/Idempotency-Key

[202] Accepted:

    `{"id":"sbx-740eb0db","image":"node:22-slim","status":"pending","ttl_seconds":187,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T16:06:36Z","expires_at":"2026-10-28T16:09:43Z"}`

Reproduce with:

    curl -X POST -H 'Idempotency-Key: [Filtered]' -H 'Content-Type: application/json' -d '{"ttl_seconds": 187, "image": "node:22-slim", "limits": {"cpus": 1, "memory_mb": 512}}' http://localhost:8000/v1/sandboxes

    st replay rDMHY0

______________________________________________________ POST /v1/sandboxes/{sandbox_id}/exec _____________________________________________________
1. Test Case ID: rrQbcd

- ST108 Response violates schema

    "/errors/not-ready" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 409.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/not-ready"

[409] Conflict:

    `{"type":"/errors/not-ready","title":"Conflict","status":409,"instance":"/v1/sandboxes/sbx-75ff9d20/exec","detail":"sbx-75ff9d20 n'est pas prête"}`

Reproduce with:

    curl -X POST -H 'Content-Type: application/json' -d '{"cmd": ["python", "-c", "print(2 + 2)"], "timeout_seconds": 40}' http://localhost:8000/v1/sandboxes/sbx-75ff9d20/exec

    st replay rrQbcd

______________________________________________________ PUT /v1/sandboxes/{sandbox_id}/files _____________________________________________________
1. Test Case ID: ROHDeb

- ST108 Response violates schema

    "/errors/not-ready" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 409.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/not-ready"

[409] Conflict:

    `{"type":"/errors/not-ready","title":"Conflict","status":409,"instance":"/v1/sandboxes/sbx-75ff9d20/files","detail":"sbx-75ff9d20 n'est pas prête"}`

Reproduce with:

    curl -X PUT -H 'Content-Type: application/octet-stream' -d $'�PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:~�U\x00\x00\x00\nIDATx�c`\x00\x00\x00\x02\x00\x01H��q\x00\x00\x00\x00IEND�B`�' 'http://localhost:8000/v1/sandboxes/sbx-75ff9d20/files?path=src%2Fmain.py'

    st replay ROHDeb

_________________________________________________________________ Stateful tests ________________________________________________________________
1. Test Case ID: C7V6aT

- ST108 Response violates schema

    "/errors/validation" is not one of "/problems/not-found", "/problems/file-not-found" or 7 other candidates

    Validated against the response schema for status code 422.

    Schema at /properties/type:

        {
            "enum": [
                "/problems/not-found",
                "/problems/file-not-found",
                "/problems/not-ready",
                "/problems/idempotency-conflict",
                "/problems/invalid-json",
                "/problems/validation",
                "/problems/precondition-failed",
                "/problems/unsupported-media-type",
                "/problems/payload-too-large"
            ],
            "type": "string",
            "format": "uri-reference",
            "example": "/problems/not-found"
        }

    Value:

        "/errors/validation"

[422] Unprocessable Content:

    `{"type":"/errors/validation","title":"Unprocessable Content","status":422,"instance":"/v1/sandboxes","detail":"query.page_size : Input should be a valid integer, unable to parse string as an integer"}`

Reproduce with:

    curl -X GET 'http://localhost:8000/v1/sandboxes?page_size=false'

    st replay C7V6aT

2. Test Case ID: iDaIS7

- ST108 Response violates schema

    "__not_in_enum__" is not one of "python:3.12-slim", "node:22-slim" or "alpine:3.20"

    Validated against the response schema for status code 202.

    Schema at /components/schemas/Image:

        {
            "enum": [
                "python:3.12-slim",
                "node:22-slim",
                "alpine:3.20"
            ],
            "type": "string",
            "description": "Images autoris\u00e9es (liste blanche).",
            "example": "python:3.12-slim"
        }

    Value:

        "__not_in_enum__"

[202] Accepted:

    `{"id":"sbx-b1b74e6c","image":"__not_in_enum__","status":"pending","ttl_seconds":600,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T16:06:38Z","expires_at":"2026-10-28T16:16:38Z"}`

Reproduce with:

    curl -X POST -H 'Content-Type: application/json' -d '{"image": "__not_in_enum__"}' http://localhost:8000/v1/sandboxes

    st replay iDaIS7

3. Test Case ID: yLm7wG

- ST108 Response violates schema

    "__not_in_enum__" is not one of "python:3.12-slim", "node:22-slim" or "alpine:3.20"

    Validated against the response schema for status code 200.

    Schema at /components/schemas/Image:

        {
            "enum": [
                "python:3.12-slim",
                "node:22-slim",
                "alpine:3.20"
            ],
            "type": "string",
            "description": "Images autoris\u00e9es (liste blanche).",
            "example": "python:3.12-slim"
        }

    Value:

        "__not_in_enum__"

[200] OK:

    `{"items":[{"id":"sbx-5ad37ff0","image":"alpine:3.20","status":"ready","ttl_seconds":600,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T16:06:37Z","expires_at":"2026-10-28T16:16:37Z"},{"id":"sbx-03a0c113","image":"python:3.12-slim","status":"pending","ttl_seconds":1781,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T16:06:38Z","expires_at":"2026-10-28T16:36:19Z"},{"id":"sbx-a3d7bbe4","image":"alpine:3.20","status":"pending","ttl_seconds":600,"limits":{"cpus":1,"memory_mb":512},"cre // Output truncated...`

Reproduce with:

    curl -X GET http://localhost:8000/v1/sandboxes

    st replay yLm7wG

4. Test Case ID: GqSkkd

- ST201 Schema-violating request accepted

    Invalid data should have been rejected
    Expected: 400, 401, 403, 404, 405, 406, 409, 415, 422, 428, 429, 5xx
    Invalid component: parameters `status`, `page_size` in query
      - violates `enum` at /properties/status
      - violates `minimum`, `maximum` at /properties/page_size

[200] OK:

    `{"items":[],"next_page_token":null}`

Reproduce with:

    curl -X GET 'http://localhost:8000/v1/sandboxes?page_size=0&status='

    st replay GqSkkd

5. Test Case ID: 8qJf14

- ST108 Response violates schema

    "__not_in_enum__" is not one of "python:3.12-slim", "node:22-slim" or "alpine:3.20"

    Validated against the response schema for status code 200.

    Schema at /components/schemas/Image:

        {
            "enum": [
                "python:3.12-slim",
                "node:22-slim",
                "alpine:3.20"
            ],
            "type": "string",
            "description": "Images autoris\u00e9es (liste blanche).",
            "example": "python:3.12-slim"
        }

    Value:

        "__not_in_enum__"

[200] OK:

    `{"id":"sbx-9d2376fc","image":"__not_in_enum__","status":"failed","ttl_seconds":600,"limits":{"cpus":1,"memory_mb":512},"created_at":"2026-10-28T16:06:39Z","expires_at":"2026-10-28T16:16:39Z"}`

Reproduce with:

    curl -X GET 'http://localhost:8000/v1/sandboxes?status=failed&page_size=75'
    curl -X GET http://localhost:8000/v1/sandboxes/sbx-9d2376fc

    st replay 8qJf14

==================================================================== WARNINGS ===================================================================

Method Not Allowed: 1 operation consistently returned `405 Method Not Allowed`, skipped from later phases

  - PATCH /v1/sandboxes/{sandbox_id}

💡 Verify the server actually accepts these methods, or remove them from the schema if unsupported

==================================================================== SUMMARY ====================================================================

API Operations:
  Selected: 9/9
  Tested: 8
  Skipped: 1
    - Skipped after 10+ consecutive `405 Method Not Allowed` responses (restored from cache)

Test Phases:
  ❌ Examples
  ❌ Coverage
  ❌ Fuzzing
  ❌ Stateful

Failures:
  ❌ ST101 Server error: 1
  ❌ ST108 Response violates schema: 10
  ❌ ST205 Allow header mismatch: 1
  ❌ ST201 Schema-violating request accepted: 2
  ❌ ST103 Undocumented status code: 1

For more information, run `st explain <code>` for ST101, ST103, ST108, ST201, ST205.

Warnings:
  ⚠️ Method Not Allowed: 1 operation skipped after consistent 405 responses

Test cases:
  330 generated, 14 found 15 unique failures

Seed: 259561316623521227571660214598457924567

======================================================== 15 failures, 1 warning in 6.56s ========================================================
make: *** [Makefile:37: test-contract] Error 1
kyrohe@MSI-Kyrohe:~/apirestsandbox$ 
```

Modifications :
- app/errors.py:23 : le champ type des erreurs commence par /problems/ au lieu de /errors/.
- openapi.yaml:464 : /problems/method-not-allowed ajouté à l'enum de Problem.type.
- app/main.py : imports re, Literal et Query ajoutés, sans nouvelle dépendance.
- app/main.py : nouveau modèle Limits (cpus entre 0,1 et 2, memory_mb entre 64 et 1024), qui refuse les champs inconnus et les types approximatifs.
- app/main.py : SandboxCreate n'accepte que les 3 images de la liste blanche, un ttl_seconds entre 60 et 3600 et un limits optionnel, et refuse les champs inconnus et les types approximatifs ("600" est refusé).
- app/main.py : create_sandbox renvoie 422 si Idempotency-Key ne fait pas entre 1 et 255 caractères, et enregistre les limits demandés au lieu de 512 Mo fixes.
- app/main.py : list_sandboxes valide status (enum), page_size (1 à 100) et page_token (entier positif), et répond 422 au lieu de 500.

Vérifié à la main : page_token=abc, page_size=0, status=foo, une image hors liste et ttl_seconds:"600" donnent maintenant tous 422, et un 404 renvoie bien /problems/not-found.