# ADR-0006 — Pool defaults tuned for serverless PostgreSQL (Neon)

- Status: accepted (retro-documented)
- Date of evidence: 2026-10-29 (commits dbada06, 679d01d)

## Decision
pool ตรวจ connection ก่อนส่งให้ (`check=ConnectionPool.check_connection`), รอ acquire 20 s, connect timeout 15 s, max_lifetime 1800 s, max_idle 300 s

## Evidence
- src/platform_backend_core/db.py (comment "Neon: ~5-10 s")
- docs/runtime.md (Pools default …)
- runtime_tests/test_database.py (`test_pool_replaces_a_connection_the_server_closed`, `test_defaults_allow_a_serverless_database_to_wake_up`)
- ops record: book-platforms-status (2026-11-03) "Core fixes found in production … Neon suspends idle compute after 5 minutes … takes about 6–9 s to resume"

## Consequences
- request แรกหลัง compute หลับช้าได้ถึง ~15 s; consumer ต้องตั้ง request deadline ให้พอ
