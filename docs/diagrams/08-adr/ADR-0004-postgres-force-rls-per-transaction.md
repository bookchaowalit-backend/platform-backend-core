# ADR-0004 — Tenant isolation by PostgreSQL FORCE RLS with a per-transaction workspace setting

- Status: accepted (retro-documented)

## Decision
`Database.transaction(workspace)` ผูก `app.workspace_id` ด้วย `set_config(..., true)` ต่อ transaction; runtime role ต้องเป็น
`NOSUPERUSER NOBYPASSRLS` (ตรวจทุก connection ใหม่); pool reset ล้างค่า; tenant table ต้อง ENABLE + FORCE RLS พร้อม USING/WITH CHECK

## Evidence
- src/platform_backend_core/db.py (`_configure`, `_reset`, `transaction`)
- docs/runtime.md (Transactions and RLS + SQL ตัวอย่าง)
- runtime_tests/test_database.py (`test_rls_transaction_pool_reuse_and_rollback`, `test_database_refuses_privileged_runtime_role`)

## Consequences
- policy SQL เป็นความรับผิดชอบของ consumer migration; core ไม่ตรวจว่าตารางมี RLS
- API เป็น synchronous; ห้ามเรียกใน async handler โดยตรง
