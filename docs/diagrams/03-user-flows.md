# 03 — User flows (ต่อ role)

ไม่มี UI/pages; flow คือเส้นทางที่แต่ละ actor ใช้ library

## Service developer: ต่อ runtime เข้า service

```mermaid
flowchart TD
    A["pip / uv install core from git SHA"] --> B["TokenVerifier with issuer, audience and exactly one key source"]
    B --> C["Database with runtime DSN"]
    C --> D["create_app service_name, database, verifier"]
    D --> E["Register app.state.readiness_checks e.g. schema version"]
    E --> F["Route uses Depends require_scope"]
    F --> G["Handler opens database.transaction principal.workspace"]
    G --> H["Serve with fixed worker count; migrations run separately"]
```

Sources: docs/runtime.md (Installation, HTTP integration), src/platform_backend_core/http.py, db.py, auth.py

## Caller: request ผ่าน consumer

```mermaid
flowchart TD
    A["HTTP request with Authorization: Bearer"] --> B{"Body within limit and deadline?"}
    B -->|no| B1["413 / 504 / 400"]
    B -->|yes| C{"Token valid RS256, iss, aud, ws, exp, no del/obo?"}
    C -->|no| C1["401 unauthorized"]
    C -->|yes| D{"Scope present?"}
    D -->|no| D1["403 forbidden"]
    D -->|yes| E["Handler runs in RLS transaction"]
    E --> F["Response + generated X-Request-ID"]
```

Sources: src/platform_backend_core/http.py, auth.py, runtime_tests/test_http.py

## Operator: migration

```mermaid
flowchart TD
    A["Set DATABASE_MIGRATION_DSN in env"] --> B["platform-migrate DIR --namespace NAME"]
    B --> C{"History matches supplied SQL checksums?"}
    C -->|no| C1["exit 1: migration failed (no DSN or DB text)"]
    C -->|yes| D["Apply pending SQL + history rows in one transaction"]
    D --> E["applied N migrations"]
```

Sources: src/platform_backend_core/migrations.py, docs/runtime.md (Explicit migrations)

## Service-to-service caller: service token

```mermaid
flowchart TD
    A["ServiceTokenSource token_url, client_id, private key, audience, scope"] --> B["authorization()"]
    B --> C{"Cached token before renew time?"}
    C -->|yes| G["Bearer token"]
    C -->|no| D["Sign 60 s private_key_jwt assertion, POST client_credentials"]
    D -->|200 valid| G
    D -->|failure| E{"Old token still valid?"}
    E -->|yes| G
    E -->|no| F["ServiceTokenError; retry after 30 s"]
```

Sources: src/platform_backend_core/service_token.py, platform-workflow/src/platform_workflow/cli.py (consumer example, sibling repo)

## Maintainer: schema change — ดู [01-business-process.md](01-business-process.md) flow A (reused)

## Open questions

- ไม่มี
