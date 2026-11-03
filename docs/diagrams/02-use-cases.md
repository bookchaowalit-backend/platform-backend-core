# 02 — Use cases

Actors คือ "ผู้ใช้" จริงของ library นี้: consuming service (และ developer ของมัน), CI ของ platform repo, operator ที่รัน migration,
maintainer ของ core และ external system (identity, PostgreSQL) ไม่มี end-user ตรง — end user/caller ของ consumer ถูกแทนด้วย
"Authenticated caller" ที่ถือ RS256 workspace token

```mermaid
flowchart LR
    caller(["Authenticated caller: human or service token"])
    svc(["Consuming platform service developer"])
    ops(["Operator / release step"])
    maint(["Core maintainer"])
    pci(["Platform repo CI"])
    tester(["Test author"])
    idp(["platform-identity: JWKS and /v1/token"])
    pg(["PostgreSQL 16+"])

    subgraph core["platform-backend-core"]
        UC1["Verify workspace JWT to Principal"]
        UC2["Require scope on a route"]
        UC3["Run SQL in a workspace-scoped RLS transaction"]
        UC4["Serve /healthz, /readyz, /metrics"]
        UC5["Bound request body and deadline"]
        UC6["Apply explicit checksummed migrations"]
        UC7["Get service token via client_credentials"]
        UC8["Create disposable test database and role"]
        UC9["Validate contract schema, pin and fixtures"]
        UC10["Compare sibling platform schema copies"]
    end

    caller --> UC2
    UC2 --> UC1
    svc --> UC3
    svc --> UC4
    svc --> UC5
    svc --> UC7
    ops --> UC6
    tester --> UC8
    maint --> UC9
    maint --> UC10
    pci --> UC9
    UC1 --> idp
    UC7 --> idp
    UC3 --> pg
    UC6 --> pg
    UC8 --> pg
```

Sources: src/platform_backend_core/__init__.py, auth.py, http.py, db.py, migrations.py, service_token.py, testing.py, scripts/check.py, scripts/check_platform_sync.py, docs/runtime.md, contracts/README.md

| Actor | ระดับสิทธิ์ใน code |
|---|---|
| Authenticated caller | RS256 token: `sub`, `ws` (UUID), `scope` space-separated; ไม่มี scope = ไม่มีสิทธิ์; `del`/`obo` ถูกปฏิเสธ (auth.py) |
| Consuming service | runtime DB role ต้อง `NOSUPERUSER NOBYPASSRLS` (db.py `_configure`) |
| Operator | migration DSN แยก (`--dsn-env DATABASE_MIGRATION_DSN`) เป็นเจ้าของ DDL (migrations.py, runtime.md) |
| Test author | admin DSN ที่ create/drop DB/role ได้ (testing.py) |

Sources: src/platform_backend_core/auth.py, db.py, migrations.py, testing.py, docs/runtime.md

## Open questions

- ไม่มี

