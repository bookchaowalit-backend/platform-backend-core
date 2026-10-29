import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
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
        with pytest.raises(RuntimeError), db.transaction(a) as conn:
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
    from psycopg_pool import PoolTimeout
    # _configure rejects the superuser connection, so the pool never yields one.
    with pytest.raises(PoolTimeout):
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
    with pytest.raises(psycopg.errors.DivisionByZero):
        core().MigrationRunner(dsn).apply([migration,core().Migration('002','CREATE TABLE lost (value integer); SELECT 1/0')])
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT to_regclass('lost')").fetchone() == (None,)


def test_pool_bounds_and_workspace_type():
    with pytest.raises(ValueError):
        core().Database('postgresql://unused', max_size=0)


def test_pool_exhaustion_is_bounded(db_env):
    import time

    from psycopg_pool import PoolTimeout
    db = core().Database(db_env[1], max_size=1, timeout=.1)
    try:
        with db.transaction(uuid4()):
            start = time.monotonic()
            with pytest.raises(PoolTimeout), db.transaction(uuid4()):
                pass
            assert time.monotonic() - start < 1
    finally:
        db.close()


def test_first_migrations_in_different_namespaces_share_safe_history_initialization(db_env):
    import time
    dsn = db_env[2]
    gate = int(uuid4().hex[:14],16)
    first_dsn = make_conninfo(dsn, application_name='core_test_migration_a')
    second_dsn = make_conninfo(dsn, application_name='core_test_migration_b')
    def wait_for_lock(conn, application):
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            if conn.execute("SELECT 1 FROM pg_stat_activity WHERE application_name=%s AND wait_event_type='Lock'",(application,)).fetchone():
                return
            time.sleep(.01)
        pytest.fail(f'{application} did not reach controlled database lock')
    with psycopg.connect(dsn, autocommit=True) as coordinator, ThreadPoolExecutor(max_workers=2) as executor:
        coordinator.execute('SELECT pg_advisory_lock(%s)',(gate,))
        first = executor.submit(core().MigrationRunner(first_dsn, namespace='first').apply,
                                [core().Migration('001',f'SELECT pg_advisory_xact_lock({gate}); CREATE TABLE first_probe (id integer)')])
        try:
            wait_for_lock(coordinator,'core_test_migration_a')
            second = executor.submit(core().MigrationRunner(second_dsn, namespace='second').apply,
                                     [core().Migration('001','CREATE TABLE second_probe (id integer)')])
            wait_for_lock(coordinator,'core_test_migration_b')
        finally:
            coordinator.execute('SELECT pg_advisory_unlock(%s)',(gate,))
        assert first.result(timeout=5) == ['001']
        assert second.result(timeout=5) == ['001']
        assert coordinator.execute('SELECT namespace,version FROM platform_schema_migrations ORDER BY namespace').fetchall() == [('first','001'),('second','001')]


def test_pool_replaces_a_connection_the_server_closed(db_env):
    # Serverless Postgres (e.g. Neon suspending idle compute) closes pooled connections;
    # the next request must get a working connection, not a one-off failure.
    admin_dsn, dsn, _, _, _ = db_env
    tenant_table(dsn)
    db = core().Database(dsn, min_size=1, max_size=1)
    try:
        with db._pool.connection() as conn:
            pid = conn.info.backend_pid
        with psycopg.connect(admin_dsn) as admin:
            assert admin.execute('SELECT pg_terminate_backend(%s)', (pid,)).fetchone()[0] is True
        assert db.ready() is True
        with db.transaction(uuid4()) as conn:
            assert conn.execute('SELECT 1').fetchone() == (1,)
            assert conn.info.backend_pid != pid
    finally:
        db.close()
