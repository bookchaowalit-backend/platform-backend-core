"""Explicit disposable PostgreSQL fixtures; never discover credentials or environments."""
from contextlib import contextmanager
from dataclasses import dataclass
import re
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo


@dataclass(frozen=True)
class TemporaryDatabase:
    admin_dsn: str
    runtime_dsn: str
    runtime_role: str

    def grant_schema(self, schema='public'):
        """Grant runtime DML after migrations, without ownership or RLS bypass."""
        with psycopg.connect(self.admin_dsn) as conn:
            for template in ('GRANT USAGE ON SCHEMA {} TO {}',
                             'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}',
                             'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}'):
                conn.execute(sql.SQL(template).format(sql.Identifier(schema),sql.Identifier(self.runtime_role)))


@contextmanager
def temporary_database(admin_dsn: str, *, prefix='platform_test_'):
    """Create an isolated database and NOLOGIN role via an explicitly supplied local admin DSN.

    Runtime connections use SET ROLE through connection options. The admin connection
    must be able to create/drop databases and roles. Never pass a production DSN.
    """
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,20}', prefix):
        raise ValueError('invalid test resource prefix')
    name = prefix + uuid4().hex
    role = name + '_role'
    created_role = created_database = False
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS').format(sql.Identifier(role)))
            created_role = True
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created_database = True
        isolated_dsn = make_conninfo(admin_dsn, dbname=name)
        runtime_dsn = make_conninfo(isolated_dsn, options=f'-c role={role}')
        yield TemporaryDatabase(isolated_dsn, runtime_dsn, role)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            if created_database:
                conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
            if created_role:
                conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
