# 05 — C4 Context

library ไม่มี runtime ของตัวเอง; context จึงแสดง core **ภายใน** consumer services และระบบรอบ ๆ

```mermaid
C4Context
    title platform-backend-core in its context
    Person(maint, "Core maintainer", "Changes schema and runtime")
    Person(caller, "Authenticated caller", "Human or service with RS256 workspace token")
    System(core, "platform-backend-core", "Canonical contract schema + Python runtime library")
    System_Ext(consumers, "Platform services", "commerce, communication, data, developer, logistics, media, payment, security, workflow (+ identity tests)")
    System_Ext(platrepos, "Platform repos CI", "Vendor schema + sha256 pin")
    System_Ext(identity, "platform-identity", "Issuer, JWKS, /v1/token")
    SystemDb_Ext(pg, "PostgreSQL 16+", "Per-service DB, Neon in production")
    System_Ext(gh, "GitHub", "Source host, Actions, git+https install")

    Rel(maint, core, "Commits")
    Rel(core, gh, "Hosted on")
    Rel(consumers, core, "Installs at pinned git SHA")
    Rel(platrepos, core, "Copies schema + pin from")
    Rel(caller, consumers, "HTTPS with Bearer token")
    Rel(consumers, identity, "JWKS fetch / client_credentials via core")
    Rel(consumers, pg, "RLS transactions via core")
```

Sources: README.md, PRODUCT.md, contracts/README.md, docs/DECISION.md, docs/runtime.md, src/platform_backend_core/auth.py, service_token.py, db.py; consumer pins in sibling repos (platform-*/pyproject.toml); ops record: book-platforms-status (2026-11-03) for identity issuer/JWKS and Neon

## Open questions

- PRODUCT.md ระบุ consumers แค่ data, security, workflow — แต่ origin/main ของ 9 repo pin core แล้ว (ดู 16) ควรอัปเดต PRODUCT.md
