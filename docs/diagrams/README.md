# Core 22 SDLC diagram pack — platform-backend-core

ชุดภาพ 22 รายการตาม SDLC Diagram Catalog v2 (knowledge-base `knowledge/tech/core-cs/sdlc-diagram-catalog.md`)
วาดจากโค้ดและ config ของ repo นี้ ณ `origin/main` `dc1fa7d` (2026-11-03). repo นี้เป็น **library + canonical contract schema**
ไม่มี hosted runtime: actors = consuming services, C4 แสดง library ภายใน consumer, 16 = การ pin ด้วย git SHA
ทุก diagram มี `Sources:`; สิ่งที่ไม่รู้อยู่ใน "Open questions" ของไฟล์นั้น; ข้อมูล hosting อ้าง `ops record: book-platforms-status (2026-11-03)`
consumer pins อ่านจาก sibling worktrees `~/work/core22/platform-*` (origin/main 2026-11-03)

| # | Item | Status | File | Sources read |
|---|---|---|---|---|
| 01 | Business process (As-Is / To-Be) | done | [01-business-process.md](01-business-process.md) | contracts/README.md, scripts/check*.py, ci.yml, docs/UPGRADE-PLAN.md, docs/DECISION.md |
| 02 | Use cases | done | [02-use-cases.md](02-use-cases.md) | src/platform_backend_core/*.py, scripts/*.py, docs/runtime.md |
| 03 | User (caller) flows | done | [03-user-flows.md](03-user-flows.md) | http.py, auth.py, db.py, migrations.py, service_token.py, docs/runtime.md |
| 04 | Traceability (RTM) | done | [04-traceability.md](04-traceability.md) | PRODUCT.md, contracts/README.md, docs/runtime.md, tests/, runtime_tests/, ci.yml |
| 05 | C4 Context | done | [05-c4-context.md](05-c4-context.md) | README.md, PRODUCT.md, DECISION.md, consumer pyproject.toml, ops record |
| 06 | C4 Container | done | [06-c4-container.md](06-c4-container.md) | pyproject.toml, src/, contracts/, scripts/ |
| 07 | C4 Component | done | [07-c4-component.md](07-c4-component.md) | src/platform_backend_core/*.py |
| 08 | ADRs (retro-documented) | done | [08-adr/](08-adr/) — [0001](08-adr/ADR-0001-canonical-contract-schema-sha256-pin.md), [0002](08-adr/ADR-0002-distribute-by-pinned-git-commit.md), [0003](08-adr/ADR-0003-rs256-workspace-token-profile.md), [0004](08-adr/ADR-0004-postgres-force-rls-per-transaction.md), [0005](08-adr/ADR-0005-explicit-migrations-never-at-startup.md), [0006](08-adr/ADR-0006-serverless-postgres-pool-defaults.md) | code, docs/, git log, consumer pins, ops record |
| 09 | ERD | done | [09-erd.md](09-erd.md) | migrations.py, docs/runtime.md, contract schema |
| 10 | Sequences | done | [10-sequences.md](10-sequences.md) | http.py, auth.py, db.py, service_token.py, migrations.py |
| 11 | State machines | done | [11-state-machines.md](11-state-machines.md) | service_token.py, auth.py, migrations.py, contract schema |
| 12 | API & integrations | done | [12-api-integration.md](12-api-integration.md) | http.py, auth.py, service_token.py, docs/runtime.md |
| 13 | Threat model | done | [13-threat-model.md](13-threat-model.md) | src/*.py, ci.yml, docs/runtime.md, branch protection API |
| 14 | Backup & DR | not_applicable (library, no datastore; consumer DBs covered in their packs) | [14-backup-dr.md](14-backup-dr.md) | PRODUCT.md, contracts/README.md, migrations.py |
| 15 | CI/CD pipeline | done | [15-cicd-pipeline.md](15-cicd-pipeline.md) | .github/workflows/ci.yml, README.md, gh run list |
| 16 | Deployment (distribution) | done | [16-deployment.md](16-deployment.md) | consumer pyproject.toml/Dockerfile, docs/runtime.md, ops record |
| 17 | Test coverage matrix | done | [17-test-coverage-matrix.md](17-test-coverage-matrix.md) | tests/, runtime_tests/, ci.yml, pyproject.toml |
| 18 | Git & release workflow | done | [18-git-release-workflow.md](18-git-release-workflow.md) | git log, gh pr list, branch protection API |
| 19 | Service dependency map | done | [19-service-dependency-map.md](19-service-dependency-map.md) | pyproject.toml, uv.lock, ci.yml |
| 20 | Observability | done (signals provided to consumers) | [20-observability.md](20-observability.md) | http.py, PRODUCT.md, ops record |
| 21 | Incident response | done (consumer-side reality) | [21-incident-response.md](21-incident-response.md) | git log, db.py, ops record |
| 22 | DORA | done (recovery time = cannot compute; change fail inferred) | [22-dora.md](22-dora.md) | git log, gh run list |

## Reused docs (ลิงก์ ไม่คัดลอก)

- Runtime interface, RLS, migrations, HTTP limits: [docs/runtime.md](../runtime.md) — ใช้ใน 02–04, 08–13
- Schema change procedure + contract fields: [contracts/README.md](../../contracts/README.md) — ใช้ใน 01, 09
- Keep decision BOO-154: [docs/DECISION.md](../DECISION.md) — ใช้ใน 01, 08
- Backlog / To-Be: [docs/UPGRADE-PLAN.md](../UPGRADE-PLAN.md) — ใช้ใน 01
- Central architecture-docs: ไม่มีส่วนของ platform-backend-core (grep `backend-core` ใน docs/architecture ไม่พบ)
