# ADR-0005 — Explicit checksummed migrations, never at application startup

- Status: accepted (retro-documented)

## Decision
migration รันแยกด้วย `MigrationRunner` / CLI `platform-migrate` ด้วย DSN แยก; ล็อก advisory ของ shared history ก่อน namespace;
history `platform_schema_migrations` เก็บ SHA-256; ประวัติเปลี่ยน/หาย/แทรกย้อน = `MigrationDriftError`; ใช้ transaction เดียว;
`create_app` lifespan ไม่รัน migration

## Evidence
- src/platform_backend_core/migrations.py, src/platform_backend_core/http.py (`lifespan` only closes pool), src/platform_backend_core/__init__.py docstring
- docs/runtime.md (Explicit migrations)
- runtime_tests/test_database.py (`test_migration_atomicity_drift_and_concurrent_lock`, `test_first_migrations_in_different_namespaces_*`)
- commit cc710f7 "serialize migration history"

## Consequences
- ห้าม `CREATE INDEX CONCURRENTLY` / manual transaction ในไฟล์ migration
- consumer ต้องเพิ่ม readiness check ของ schema version เอง
