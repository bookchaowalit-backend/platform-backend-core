"""Shared backend primitives with explicit configuration and no startup migrations."""
from .auth import AuthenticationError, Principal, TokenVerifier
from .db import Database
from .http import create_app, require_scope
from .migrations import Migration, MigrationDriftError, MigrationRunner
from .service_token import ServiceTokenError, ServiceTokenSource

__all__ = [
    'AuthenticationError',
    'Database',
    'Migration',
    'MigrationDriftError',
    'MigrationRunner',
    'Principal',
    'ServiceTokenError',
    'ServiceTokenSource',
    'TokenVerifier',
    'create_app',
    'require_scope',
]
