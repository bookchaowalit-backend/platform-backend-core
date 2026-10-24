"""Explicit RS256 workspace tokens; never import the owner-only SDK profile."""
import json
import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

import jwt

_SCOPE = re.compile(r'[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}\Z')


class AuthenticationError(ValueError):
    """Invalid credentials. Details intentionally do not include token content."""


@dataclass(frozen=True, slots=True)
class Principal:
    actor: UUID
    workspace: UUID
    scopes: frozenset[str]
    channel: str = 'api'

    def __post_init__(self):
        if not isinstance(self.actor, UUID) or not isinstance(self.workspace, UUID):
            raise TypeError('actor and workspace must be UUIDs')
        if not isinstance(self.scopes, frozenset) or any(not isinstance(s, str) or not _SCOPE.fullmatch(s) for s in self.scopes):
            raise ValueError('invalid scopes')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _JWKS:
    """At most one refresh per 60 seconds, including unknown-key/failed requests."""
    def __init__(self, url):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('JWKS requires a configured HTTPS URL')
        self.url, self.keys, self.refresh_at = url, {}, 0.0
        self.lock = threading.Lock()

    def __call__(self, header):
        kid = header.get('kid')
        if not isinstance(kid, str) or not 1 <= len(kid) <= 256:
            raise AuthenticationError('invalid credentials')
        with self.lock:
            now = time.monotonic()
            if now >= self.refresh_at:
                self.refresh_at = now + 60
                # Old keys are not trusted indefinitely after a failed refresh.
                self.keys = {}
                with build_opener(_NoRedirect).open(Request(self.url, headers={'Accept':'application/json'}), timeout=5) as response:
                    raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ValueError('JWKS too large')
                keys = json.loads(raw)['keys']
                if not isinstance(keys, list) or len(keys) > 64:
                    raise ValueError('invalid JWKS')
                validated_keys, identifiers = {}, set()
                for key in keys:
                    if not isinstance(key, dict):
                        # Malformed remote document, not a caller type error; verify() maps it to AuthenticationError.
                        raise ValueError('invalid JWKS entry')  # noqa: TRY004
                    identifier = key.get('kid')
                    if not isinstance(identifier, str) or not 1 <= len(identifier) <= 256:
                        raise ValueError('invalid key identifier')
                    if identifier in identifiers:
                        raise ValueError('duplicate key identifier')
                    identifiers.add(identifier)
                    if key.get('kty') == 'RSA' and key.get('alg', 'RS256') == 'RS256' and key.get('use', 'sig') == 'sig':
                        validated_keys[identifier] = jwt.PyJWK.from_dict(key).key
                # Publish only a completely validated response; any failure leaves
                # the cache empty for the rest of the bounded refresh interval.
                self.keys = validated_keys
            if kid not in self.keys:
                raise AuthenticationError('invalid credentials')
            return self.keys[kid]


class TokenVerifier:
    def __init__(self, *, issuer: str, audience: str, public_key: str | bytes | None = None,
                 key_source: Callable[[dict], str | bytes] | None = None, jwks_url: str | None = None,
                 max_token_lifetime: int = 3600, leeway: int = 0):
        if not isinstance(issuer, str) or not issuer or not isinstance(audience, str) or not audience:
            raise ValueError('issuer and audience required')
        if sum(v is not None for v in (public_key, key_source, jwks_url)) != 1:
            raise ValueError('configure exactly one verification key source')
        if isinstance(max_token_lifetime, bool) or not isinstance(max_token_lifetime, int) or not 1 <= max_token_lifetime <= 86400:
            raise ValueError('token lifetime must be 1..86400 seconds')
        if isinstance(leeway, bool) or not isinstance(leeway, int) or not 0 <= leeway <= 60:
            raise ValueError('leeway must be 0..60 seconds')
        if public_key is not None:
            public_key = jwt.algorithms.get_default_algorithms()['RS256'].prepare_key(public_key)
            if hasattr(public_key, 'private_numbers'):
                raise ValueError('provide a public verification key')
        if key_source is not None and not callable(key_source):
            raise ValueError('key_source must be callable')
        self.issuer, self.audience = issuer, audience
        self.public_key = public_key
        self.key_source = _JWKS(jwks_url) if jwks_url is not None else key_source
        self.max_token_lifetime, self.leeway = max_token_lifetime, leeway

    def verify(self, authorization: str | None) -> Principal:
        try:
            if not isinstance(authorization, str) or len(authorization) > 16384:
                raise ValueError('missing authorization')
            scheme, token = authorization.split(' ')
            if scheme.lower() != 'bearer' or not token:
                raise ValueError('invalid authorization')
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or header.get('crit'):
                raise ValueError('unsupported signature')
            key: Any = self.key_source(header) if self.key_source else self.public_key
            data = jwt.decode(token, key, algorithms=['RS256'], issuer=self.issuer, audience=self.audience,
                              leeway=self.leeway, options={'require':['sub','ws','iat','exp','jti','iss','aud'], 'strict_aud': True})
            # Shared services cannot enforce delegation status or revocation.
            # Presence, including null/partial claims, is unsupported authority.
            if 'del' in data or 'obo' in data:
                raise ValueError('unsupported delegation')
            for name in ('iat','exp','nbf'):
                if name in data and (type(data[name]) not in (int,float) or not math.isfinite(data[name])):
                    raise ValueError('invalid token time')
            if not 0 < data['exp'] - data['iat'] <= self.max_token_lifetime:
                raise ValueError('invalid token lifetime')
            if data['iat'] < 0 or data.get('nbf', data['iat']) > data['exp']:
                raise ValueError('invalid token time')
            if not isinstance(data['jti'], str) or not 1 <= len(data['jti']) <= 256 or any(c.isspace() for c in data['jti']):
                raise ValueError('invalid token identifier')
            actor, workspace = UUID(data['sub']), UUID(data['ws'])
            raw_scopes = data.get('scope', '')
            if not isinstance(raw_scopes, str) or len(raw_scopes) > 8192:
                raise ValueError('invalid scope')
            scopes = raw_scopes.split(' ') if raw_scopes else []
            if len(scopes) > 128 or any(not _SCOPE.fullmatch(s) for s in scopes):
                raise ValueError('invalid scope')
            return Principal(actor, workspace, frozenset(scopes))
        except Exception:  # noqa: BLE001  fail closed: any verification failure is an opaque auth error
            raise AuthenticationError('invalid credentials') from None
