# Shared workspace runtime

Status: implemented and locally tested; production activation belongs to each service.
Correlation: `SHARED-INFRA-2026-10-15`. Python >=3.12, PostgreSQL >=16.
This package has no hub or private platform-module dependency. Existing canonical
contract schemas and offline checks remain independent of runtime dependencies.

## Installation

```bash
python -m pip install 'platform-backend-core @ git+https://github.com/bookchaowalit-backend/platform-backend-core.git@<reviewed-commit>'
# local development from this repository:
python -m pip install -e '.[test]'
```

Release consumers pin an immutable reviewed commit or wheel. Do not use a hub
absolute path as a deployed dependency. No payment, email or model provider SDK
is required.

## Stable public interface

```python
from uuid import UUID
from platform_backend_core import (
    AuthenticationError, Principal, TokenVerifier, Database,
    Migration, MigrationRunner, MigrationDriftError, create_app, require_scope,
)

Principal(actor: UUID, workspace: UUID, scopes: frozenset[str], channel: str = 'api')
TokenVerifier(*, issuer: str, audience: str,
              public_key: str | bytes | None = None,
              key_source: Callable[[dict], str | bytes] | None = None,
              jwks_url: str | None = None,
              max_token_lifetime: int = 3600, leeway: int = 0)
TokenVerifier.verify(authorization: str | None) -> Principal
Database(dsn: str, min_size: int = 0, max_size: int = 8,
         *, timeout: float = 5.0, statement_timeout_ms: int = 10000)
Database.transaction(workspace: UUID)  # context manager yielding psycopg.Connection
Database.ready() -> bool
Database.close() -> None
Migration(version: str, sql: str)  # immutable; checksum property is SHA-256
MigrationRunner(dsn: str, *, namespace: str = 'platform')
MigrationRunner.apply(migrations: Sequence[Migration]) -> list[str]
create_app(service_name: str, database: Database, verifier: TokenVerifier,
           *, max_body_bytes: int = 1048576, request_timeout: float = 30.0) -> FastAPI
require_scope(scope: str)  # FastAPI dependency factory returning Principal
```

`Principal` is frozen. Actor/workspace must be UUID objects and scopes must be
an immutable set of concrete scopes. `verify` raises a generic
`AuthenticationError` without including credentials. The only trusted workspace
comes from the signed `ws` UUID; request headers and bodies never set it.
`sub` is also a UUID. RS256, exact issuer and single audience, `sub`, `ws`,
`iat`, `exp`, `jti`, finite numeric times, and a positive bounded lifetime are
required. Optional `nbf` is verified. Boolean times, wildcards, malformed scope
strings and empty identifiers fail closed. Scope is a space-separated `scope`
claim; omission produces no permissions. Maximum lifetime is configurable up
to 86400 seconds; clock leeway is 0..60 seconds. Tokens are limited to 16 KiB.
The channel is server-owned and defaults to `api`.

Configure exactly one public PEM, injected key source, or HTTPS JWKS URL.
Injected key sources receive the unverified header only to select a key; all
claims and RS256 signatures are then verified. They must return trusted public
keys without following token-supplied network URLs. JWKS uses only the configured
HTTPS endpoint, rejects redirects, limits the response to 1 MiB / 64 keys,
and has a five-second fetch timeout. Refresh is at most once per minute,
including unknown `kid` requests and failures. Rotation can therefore take one
minute to become visible. Failed refresh clears cached keys and fails closed.
Services requiring another rotation policy can inject a bounded key source.

This is a new workspace profile. It does not replace identity's shadow issuer,
owner-only `platform-auth-sdk`, delegation checks, revocation checks or the
special MCP trust profile. Service-specific policy remains with that service.

## HTTP integration

```python
from fastapi import Depends

verifier = TokenVerifier(issuer=config.issuer, audience='jobs-api',
                         public_key=config.public_key)
database = Database(config.database_dsn)
app = create_app('jobs-api', database, verifier)

@app.get('/v1/jobs')
def jobs(principal: Principal = Depends(require_scope('jobs:read'))):
    with database.transaction(principal.workspace) as conn:
        return conn.execute('SELECT id FROM jobs ORDER BY id LIMIT 100').fetchall()
```

`app.state.database` and `app.state.verifier` are available to consumers.
Lifespan shutdown closes the pool; startup never runs migrations. Liveness is
`GET /healthz`; `GET /readyz` checks database acquisition/query and returns a
generic 503 when unavailable. Services register synchronous zero-argument checks in
`app.state.readiness_checks: dict[str, Callable[[], bool]]`, for example
`app.state.readiness_checks['schema'] = schema_is_current`. Every registered
check must return exactly `True`; false results and exceptions give a generic
503 without revealing callback details. Register checks before serving traffic,
and bound each callback's dependency timeouts. Services must check their own
migration version and required adapters. Missing verifier configuration fails construction.

The request boundary buffers up to the configured body limit (also for chunked
requests), applies an overall async deadline including body receipt, returns
safe 400/413/422/500/504 errors (validation failures never echo input values), and creates its own `X-Request-ID`. Default limits
are 1 MiB / 30 seconds; maximums are 16 MiB / 300 seconds. It does not support
unbounded request streaming. A timeout after response headers have been sent
terminates that response; it cannot replace an already-started HTTP status.
Cancelling a deadline does not kill a synchronous worker thread or undo an
already committed side effect. Keep SQL/provider timeouts below the request
deadline and use durable idempotency for writes. Bound server concurrency in
the deployment and use fixed worker counts.

`GET /metrics` provides request counters by registered route template/status
and cumulative duration in Prometheus format. Logs contain route template,
status, and generated correlation ID. Unknown paths use `unmatched`; tokens,
headers, query strings, request bodies and customer IDs are never labels.
Configure the HTTP server/access logger separately to avoid raw URLs; never
attach bearer headers or signed URLs to spans. Expose diagnostics through the
service's controlled operational ingress.

## Transactions and RLS

Use a separate runtime role with `NOSUPERUSER NOBYPASSRLS`. Pool connections
reject privileged effective roles before use. Each transaction binds
`app.workspace_id` through `set_config(..., true)`. Successful contexts commit;
exceptions roll back. Pool reset clears workspace state before reuse. Raw pool
access is private and must not be used by service code. Both `transaction` and
`ready` are synchronous; call them from sync FastAPI handlers/dependencies or
an explicit bounded thread pool, never block an async handler's event loop.

Pools default to 0..8 connections, five-second acquisition/connect timeout,
bounded waiting queue (`8 * max_size`), 30-minute lifetime and five-minute idle
expiry. Pool maxima are limited to 128. SQL and idle-in-transaction timeouts
default to ten seconds (maximum five minutes). Budget total database connections
as replicas times pool size, including workers and migration connections.

Every tenant table needs a non-null UUID workspace, a leading workspace index,
`ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and `USING` plus
`WITH CHECK` policies, for example:

```sql
CREATE TABLE items (workspace_id uuid NOT NULL, id uuid NOT NULL, value text);
CREATE INDEX ON items (workspace_id, id);
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE items FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON items
USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)
WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid);
```

A missing workspace context sees no rows. FORCE RLS is still required when a
runtime role owns a table. A service must not execute client-supplied SQL or
allow callers to choose a workspace/session configuration.

## Explicit migrations

Pass all immutable migrations in lexicographically ordered, unique versions.
The runner takes the shared history-table advisory lock before the namespace
advisory lock, in the same order for every runner, and checks SHA-256 history.
Both locks remain held through commit, so different namespaces also serialize
while initializing/applying migrations. The runner applies pending SQL plus history atomically in one transaction. Changed,
missing, reordered or backfilled history fails closed. It uses a separate
explicit DSN, five-second connection timeout, 30-second statement timeout and
ten-second lock timeout. Migration SQL is trusted release code and must be
transactional; concurrent index creation and manual transaction control do not
belong in these files. Never edit an applied file; add a new version.

```bash
# Explicit release/setup command; variable is injected by the operator.
platform-migrate migrations --namespace jobs --dsn-env DATABASE_MIGRATION_DSN
```

The migration role owns DDL; grant only necessary table DML/schema usage to the
runtime role. The CLI never prints the DSN or underlying database error text.
The Python runner raises the underlying DB exception for operator-controlled
error handling. Do not expose those exceptions directly over HTTP.

## Real disposable PostgreSQL tests

```python
from platform_backend_core.testing import temporary_database

with temporary_database(explicit_local_admin_dsn, prefix='platform_test_') as test:
    MigrationRunner(test.admin_dsn).apply(migrations)
    test.grant_schema('public')
    db = Database(test.runtime_dsn)
    try:
        # test.runtime_role is NOSUPERUSER NOBYPASSRLS.
        ...
    finally:
        db.close()
```

The helper creates uniquely named databases/roles and drops only those names
on exit. The admin must be able to create/drop databases/roles. Fixture runtime
connections use the NOLOGIN runtime role through explicit connection options;
production uses a dedicated login role with its own authentication. Do not
pass production DSNs. `grant_schema` grants schema usage, table DML and sequence
usage without ownership. Run grants again after creating additional tables.

Run `python3 scripts/check.py`, `python3 -m unittest discover -s tests -v`, and
`PLATFORM_TEST_DSN=<disposable-admin-dsn> python -m pytest`. Without an explicit
DSN, database tests are visibly skipped and are not evidence of durability.
The local acceptance suite covers real pool reuse, missing context, cross-tenant
writes, rollback, pool exhaustion, effective role flags, migration concurrency,
checksum drift and transactional failure. Provider integration and production
load acceptance belong to the consuming services.


## Local verification record — 2026-10-15

The initial runtime test run failed on missing public runtime features
(27 failures, three database tests visibly skipped before the fixture DSN
arrived). The dedicated disposable-database helper test also failed before
implementation. A subsequent real PostgreSQL mutation check removed workspace
binding in memory and failed with an RLS policy violation, confirming that the
isolation test observes that boundary. Validation-payload redaction and custom
readiness tests each failed on the missing behavior before their fixes.

Final verification used Python 3.14 and rootless PostgreSQL 18 on a private
local socket, creating only unique `core_test_` databases/roles:

- `python3 scripts/check.py`: passed, canonical schemas/pins unchanged.
- `python3 -m unittest discover -s tests -v`: 17 passed.
- `PLATFORM_TEST_DSN=... python -m pytest -q`: 67 passed, seven subtests passed,
  no database skips. One upstream Starlette/httpx deprecation warning.
- Editable installation, wheel build and wheel import from an isolated target:
  passed. Wheel artifacts are ignored build outputs, not release publications.

Python 3.12/PostgreSQL 16 CI is configured but was not executed in this local
session. No provider, deployment, production load or release acceptance is
claimed by these checks.


Independent review regression checks also reproduced and fixed two boundaries:
a failed JWKS refresh never publishes a partially validated key cache, including
duplicate/malformed entries, and first migrations from different namespaces
cannot race the shared history table creation. All four new regression cases
failed before their fixes and passed afterward on the real disposable database.
