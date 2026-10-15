"""Shared backend primitives with explicit configuration and no startup migrations."""
from .auth import AuthenticationError, Principal, TokenVerifier
from .db import Database
from .http import create_app, require_scope
from .migrations import Migration, MigrationDriftError, MigrationRunner

__all__ = ['AuthenticationError', 'Principal', 'TokenVerifier', 'Database', 'create_app', 'require_scope',
           'Migration', 'MigrationDriftError', 'MigrationRunner']
