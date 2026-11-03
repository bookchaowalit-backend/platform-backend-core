# 11 — State machines

core ไม่มี entity ใน DB ที่มี status field; lifecycle ที่มีจริงในโค้ดคือ token cache ของ `ServiceTokenSource`, JWKS cache และ migration history
และ field `status` ของ contract schema (enum เท่านั้น)

## ServiceTokenSource

```mermaid
stateDiagram-v2
    [*] --> NoToken
    NoToken --> Fresh: fetch ok
    NoToken --> BackingOff: fetch fails, raise ServiceTokenError
    Fresh --> RenewDue: now >= renew_at
    RenewDue --> Fresh: fetch ok
    RenewDue --> StaleButValid: fetch fails, now < expires_at
    StaleButValid --> Fresh: retry after 30 s ok
    StaleButValid --> NoToken: now >= expires_at
    BackingOff --> NoToken: retry window reached
```

Sources: src/platform_backend_core/service_token.py (`authorization`, `_fetch`, `RETRY_AFTER_FAILURE_SECONDS`), runtime_tests/test_service_token.py

## JWKS cache

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Loaded: refresh ok
    Empty --> Empty: refresh fails, wait 60 s
    Loaded --> Refreshing: 60 s elapsed and a lookup arrives
    Refreshing --> Loaded: all entries valid
    Refreshing --> Empty: any failure clears keys
```

Sources: src/platform_backend_core/auth.py (`_JWKS.__call__`)

## Migration version (per namespace)

```mermaid
stateDiagram-v2
    [*] --> Pending: supplied, not in history
    Pending --> Applied: SQL + history row committed
    Pending --> Rejected: version sorts before max applied
    Applied --> Drift: supplied checksum differs or file missing
    Drift --> [*]: MigrationDriftError
```

Sources: src/platform_backend_core/migrations.py

## Contract `status`

schema กำหนดแค่ค่า `scaffolded`, `pilot`, `active`, `retired` ไม่มีกฎ transition ใน code (contracts/book-platform.contract.v1.schema.json)

## Open questions

- มีลำดับ transition ของ contract `status` ที่ตั้งใจไว้หรือไม่ (เช่น ห้าม retired → active)?
