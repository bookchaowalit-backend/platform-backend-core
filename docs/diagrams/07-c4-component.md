# 07 — C4 Component (package `platform_backend_core`)

```mermaid
C4Component
    title Components of platform_backend_core
    Container_Boundary(pkg, "platform_backend_core") {
        Component(auth, "auth.py", "TokenVerifier, Principal, _JWKS", "RS256 verify, strict claims, bounded JWKS cache")
        Component(http, "http.py", "create_app, require_scope, _Boundary", "Lifespan, body/deadline limits, healthz/readyz/metrics, request log")
        Component(db, "db.py", "Database", "psycopg ConnectionPool, role check, workspace set_config, reset")
        Component(mig, "migrations.py", "Migration, MigrationRunner, main", "Advisory locks, checksum history, CLI")
        Component(st, "service_token.py", "ServiceTokenSource", "private_key_jwt client_credentials, cached renewal")
        Component(test, "testing.py", "temporary_database", "Disposable DB + NOLOGIN role")
    }
    System_Ext(identity, "platform-identity")
    ContainerDb(pg, "PostgreSQL")

    Rel(http, auth, "verifier.verify, _SCOPE regex")
    Rel(http, db, "database.ready / close")
    Rel(auth, identity, "GET jwks_url")
    Rel(st, identity, "POST token_url")
    Rel(db, pg, "pool")
    Rel(mig, pg, "psycopg.connect")
    Rel(test, pg, "admin DSN")
```

Sources: src/platform_backend_core/__init__.py, auth.py, http.py, db.py, migrations.py, service_token.py, testing.py

หมายเหตุ: `http.py` import `_SCOPE` และ `AuthenticationError` จาก `auth.py`; `service_token.py` ไม่ขึ้นกับ module อื่นใน package

## Open questions

- ไม่มี
