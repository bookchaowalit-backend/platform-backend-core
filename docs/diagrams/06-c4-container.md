# 06 — C4 Container

"Containers" ของ repo นี้คือ artefacts ที่ส่งออก: Python package, CLI, contract schema bundle, และ check scripts; แสดงใน consumer service container

```mermaid
C4Container
    title platform-backend-core containers
    System_Boundary(repo, "platform-backend-core repo") {
        Container(pkg, "platform_backend_core package", "Python 3.12, FastAPI, psycopg, PyJWT", "Auth, DB, HTTP, migrations, service tokens, test fixtures")
        Container(cli, "platform-migrate", "console script", "Explicit SQL migrations from a directory")
        Container(schema, "Contract schema bundle", "JSON Schema + sha256 + examples", "contracts/")
        Container(checks, "Check scripts", "Python 3.11 stdlib", "scripts/check.py, check_platform_sync.py")
    }
    System_Boundary(svc, "A consuming platform service") {
        Container(app, "Service API", "FastAPI app from create_app", "Routes with require_scope")
        Container(mig, "Release migration step", "platform-migrate", "Run by operator")
    }
    ContainerDb(db, "Service PostgreSQL", "PostgreSQL 16+", "Tenant tables with FORCE RLS + platform_schema_migrations")
    System_Ext(identity, "platform-identity", "JWKS + /v1/token")

    Rel(app, pkg, "imports")
    Rel(mig, cli, "runs")
    Rel(app, db, "runtime role, set_config app.workspace_id")
    Rel(mig, db, "migration DSN, advisory locks")
    Rel(app, identity, "HTTPS JWKS / token POST")
    Rel(checks, schema, "validates")
```

Sources: pyproject.toml (`[project.scripts]`, dependencies), src/platform_backend_core/*.py, contracts/, scripts/check.py, scripts/check_platform_sync.py, docs/runtime.md

## Open questions

- ไม่มี
