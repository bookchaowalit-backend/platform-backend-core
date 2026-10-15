"""Explicit transactional migrations. Never invoked by application startup."""
import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

import psycopg


class MigrationDriftError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    sql: str

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', self.version) or not isinstance(self.sql, str) or not self.sql.strip():
            raise ValueError('migration requires a version and SQL')

    @property
    def checksum(self):
        return hashlib.sha256(self.sql.encode()).hexdigest()


class MigrationRunner:
    def __init__(self, dsn, *, namespace='platform'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', namespace):
            raise ValueError('invalid migration namespace')
        self.dsn, self.namespace = dsn, namespace

    def apply(self, migrations: Sequence[Migration]) -> list[str]:
        versions = [m.version for m in migrations]
        if len(versions) != len(set(versions)) or versions != sorted(versions):
            raise ValueError('migrations must have unique ordered versions')
        applied = []
        with psycopg.connect(self.dsn, connect_timeout=5) as conn:
            conn.execute('SET LOCAL statement_timeout = 30000')
            conn.execute('SET LOCAL lock_timeout = 10000')
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ('platform-migrations:'+self.namespace,))
            conn.execute('CREATE TABLE IF NOT EXISTS platform_schema_migrations (namespace text NOT NULL, version text NOT NULL, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (namespace,version))')
            existing = dict(conn.execute('SELECT version,checksum FROM platform_schema_migrations WHERE namespace=%s', (self.namespace,)).fetchall())
            supplied = {m.version:m for m in migrations}
            if any(version not in supplied or supplied[version].checksum != checksum for version, checksum in existing.items()):
                raise MigrationDriftError('migration history differs from supplied migrations')
            for migration in migrations:
                if migration.version in existing:
                    continue
                if existing and migration.version < max(existing):
                    raise MigrationDriftError('migration history cannot be inserted before existing versions')
                conn.execute(migration.sql)
                conn.execute('INSERT INTO platform_schema_migrations (namespace,version,checksum) VALUES (%s,%s,%s)', (self.namespace,migration.version,migration.checksum))
                applied.append(migration.version)
        return applied


def main():
    parser = argparse.ArgumentParser(description='Apply explicit service SQL migrations; DSN supplied by environment')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--namespace', default='platform')
    parser.add_argument('--dsn-env', default='DATABASE_MIGRATION_DSN')
    args = parser.parse_args()
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        parser.error('migration DSN environment variable is required')
    migrations = [Migration(path.stem,path.read_text()) for path in sorted(args.directory.glob('*.sql'))]
    if not migrations:
        parser.error('no SQL migrations found')
    try:
        applied = MigrationRunner(dsn, namespace=args.namespace).apply(migrations)
    except Exception:
        parser.exit(1, 'migration failed; inspect migration history and database access\n')
    print(f'applied {len(applied)} migrations')
