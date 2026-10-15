import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from test_auth import core


@pytest.fixture
def db_env():
    admin_dsn = os.environ.get('PLATFORM_TEST_DSN')
    if not admin_dsn:
        pytest.skip('PLATFORM_TEST_DSN required: real PostgreSQL check not executed')
    from platform_backend_core.testing import temporary_database
    with temporary_database(admin_dsn, prefix='core_test_') as temporary:
        with psycopg.connect(temporary.admin_dsn) as conn:
            conn.execute(sql.SQL('GRANT CREATE ON SCHEMA public TO {}').format(sql.Identifier(temporary.runtime_role)))
        yield temporary.admin_dsn, temporary.runtime_dsn, temporary.admin_dsn, 'public', temporary.runtime_role



def tenant_table(dsn):
    with psycopg.connect(dsn) as conn:
        conn.execute('CREATE TABLE items (workspace_id uuid NOT NULL, value text NOT NULL)')
        conn.execute('CREATE INDEX ON items (workspace_id)')
        conn.execute('ALTER TABLE items ENABLE ROW LEVEL SECURITY')
        conn.execute('ALTER TABLE items FORCE ROW LEVEL SECURITY')
        conn.execute("CREATE POLICY tenant ON items USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)")


def test_rls_transaction_pool_reuse_and_rollback(db_env):
    _, dsn, _, _, _ = db_env
    tenant_table(dsn)
    db = core().Database(dsn, max_size=1)
    a, b = uuid4(), uuid4()
    try:
        with db.transaction(a) as conn:
            flags = conn.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
            assert flags == (False, False)
            conn.execute('INSERT INTO items VALUES (%s, %s)', (a,'committed'))
            backend = conn.info.backend_pid
        with db.transaction(b) as conn:
            assert conn.info.backend_pid == backend
            assert conn.execute('SELECT value FROM items').fetchall() == []
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('INSERT INTO items VALUES (%s, %s)', (a,'forged'))
        with pytest.raises(RuntimeError):
            with db.transaction(a) as conn:
                conn.execute('INSERT INTO items VALUES (%s,%s)',(a,'rolled back'))
                raise RuntimeError('abort')
        with db.transaction(a) as conn:
            assert conn.execute('SELECT value FROM items').fetchall() == [('committed',)]
        with db._pool.connection() as conn:
            assert conn.execute('SELECT value FROM items').fetchall() == []
            assert conn.execute("SELECT nullif(current_setting('app.workspace_id',true),'')").fetchone() == (None,)
        assert db.ready()
    finally:
        db.close()


def test_database_refuses_privileged_runtime_role(db_env):
    with pytest.raises(Exception):
        db = core().Database(db_env[0], timeout=0.2)
        try:
            with db.transaction(uuid4()):
                pass
        finally:
            db.close()


def test_migration_atomicity_drift_and_concurrent_lock(db_env):
    _, _, dsn, _, _ = db_env
    migration = core().Migration('001', 'CREATE TABLE migration_probe (value integer)')
    def apply():
        return core().MigrationRunner(dsn).apply([migration])
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _:apply(), range(2)))
    assert sorted(results, key=len) == [[], ['001']]
    with pytest.raises(core().MigrationDriftError):
        core().MigrationRunner(dsn).apply([core().Migration('001', 'SELECT 42')])
    with pytest.raises(Exception):
        core().MigrationRunner(dsn).apply([migration,core().Migration('002','CREATE TABLE lost (value integer); SELECT 1/0')])
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT to_regclass('lost')").fetchone() == (None,)


def test_pool_bounds_and_workspace_type():
    with pytest.raises(ValueError):
        core().Database('postgresql://unused', max_size=0)


def test_pool_exhaustion_is_bounded(db_env):
    from psycopg_pool import PoolTimeout
    import time
    db = core().Database(db_env[1], max_size=1, timeout=.1)
    try:
        with db.transaction(uuid4()):
            start = time.monotonic()
            with pytest.raises(PoolTimeout):
                with db.transaction(uuid4()):
                    pass
            assert time.monotonic() - start < 1
    finally:
        db.close()
