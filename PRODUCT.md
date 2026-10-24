# platform-backend-core — Product brief

**Slug:** `bookchaowalit-backend/platform-backend-core`
**Updated:** 2026-10-24
**Status:** shared library plus contract schemas; nothing here is deployed

## Purpose

Two things live here:

1. The canonical Book Platform repository contract schema in `contracts/`,
   vendored by each platform repository and checked offline by
   `scripts/check.py`.
2. The `platform-backend-core` Python package (`src/platform_backend_core/`):
   workspace JWT verification (`TokenVerifier`, `Principal`), a PostgreSQL
   pool with a per-workspace transaction context (`Database`), explicit
   checksummed migrations (`MigrationRunner`), a FastAPI app factory with body
   and time limits (`create_app`, `require_scope`) and disposable database
   test fixtures (`testing.temporary_database`). See `docs/runtime.md`.

## Runnable path

- Offline contract checks (Python 3.11+, standard library only):
  `python3 scripts/check.py` and `python3 -m unittest discover -s tests`.
- Library: `uv sync --frozen --all-extras`, then `ruff check .`, `mypy` and
  `python -m pytest`. Set `PLATFORM_TEST_DSN` to a disposable PostgreSQL admin
  DSN to run the RLS, migration and concurrency tests; without it they skip.

## Consumers

`platform-data`, `platform-security` and `platform-workflow` install this
package from a pinned Git commit of this repository (it is not published to
PyPI).

## Limits

- No service, container or worker is built or deployed from this repository;
  it has no runtime of its own, so it does not report to Sentry.
- Schema changes must be copied to every platform repository that vendors them.
