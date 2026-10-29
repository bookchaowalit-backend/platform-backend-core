"""Bounded synchronous PostgreSQL transactions with local workspace authority."""
import math
from contextlib import contextmanager
from uuid import UUID

from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, dsn, min_size=0, max_size=8, *, timeout=5.0, statement_timeout_ms=10000):
        if type(min_size) is not int or type(max_size) is not int or not 0 <= min_size <= max_size <= 128 or max_size == 0:
            raise ValueError('pool must satisfy 0 <= min_size <= max_size <= 128')
        if not isinstance(timeout, (int,float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('timeout must be finite and <= 60 seconds')
        if type(statement_timeout_ms) is not int or not 1 <= statement_timeout_ms <= 300000:
            raise ValueError('invalid statement timeout')
        self.statement_timeout_ms = statement_timeout_ms
        self._pool = ConnectionPool(dsn, min_size=min_size, max_size=max_size, timeout=timeout,
                                    max_waiting=max_size * 8, max_lifetime=1800, max_idle=300,
                                    kwargs={'connect_timeout': max(1, math.ceil(timeout))},
                                    # Serverless Postgres closes idle connections (Neon suspends compute);
                                    # check before handing one out so the next request never gets a dead one.
                                    check=ConnectionPool.check_connection,
                                    configure=self._configure, reset=self._reset, open=True)

    def _configure(self, conn):
        privileged = conn.execute('SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user').fetchone()
        if not privileged or privileged[0]:
            raise ValueError('runtime database role must be NOSUPERUSER NOBYPASSRLS')
        conn.execute("SELECT set_config('statement_timeout', %s, false)", (str(self.statement_timeout_ms),))
        conn.execute("SELECT set_config('idle_in_transaction_session_timeout', %s, false)", (str(self.statement_timeout_ms),))
        conn.commit()

    @staticmethod
    def _reset(conn):
        conn.rollback()
        conn.execute("SELECT set_config('app.workspace_id', '', false)")
        conn.commit()

    @contextmanager
    def transaction(self, workspace: UUID):
        if not isinstance(workspace, UUID):
            raise TypeError('workspace must be a UUID from the verified principal')
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("SELECT set_config('app.workspace_id', %s, true)", (str(workspace),))
            yield conn

    def ready(self) -> bool:
        try:
            with self._pool.connection() as conn:
                return conn.execute('SELECT 1').fetchone() == (1,)
        except Exception:  # noqa: BLE001  readiness probe fails closed on any database error
            return False

    def close(self):
        self._pool.close()
