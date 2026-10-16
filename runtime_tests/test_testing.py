import os
import psycopg
import pytest
from test_auth import core


def test_disposable_database_role_and_cleanup():
    dsn = os.environ.get('PLATFORM_TEST_DSN')
    if not dsn:
        pytest.skip('real PostgreSQL unavailable')
    from platform_backend_core import testing
    with testing.temporary_database(dsn, prefix='core_test_') as temporary:
        with psycopg.connect(temporary.admin_dsn) as conn:
            database = conn.info.dbname
            conn.execute('CREATE TABLE probe (workspace_id uuid NOT NULL)')
        temporary.grant_schema('public')
        with psycopg.connect(temporary.runtime_dsn) as conn:
            assert conn.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone() == (False,False)
            assert conn.execute('SELECT * FROM probe').fetchall() == []
        role = temporary.runtime_role
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(database,)).fetchone() is None
        assert conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone() is None
