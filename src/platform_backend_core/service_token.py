"""Access tokens for a service from platform-identity's ``client_credentials`` grant.

The service signs a short, single-use ``private_key_jwt`` assertion with its own
RSA key (platform-identity docs/SERVICE-CLIENTS.md), caches the access token and
renews it before it expires. The private key and tokens are never logged,
returned in errors or shown in ``repr``.
"""
import http.client
import json
import re
import threading
import time
import uuid
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
ASSERTION_LIFETIME_SECONDS = 60
RETRY_AFTER_FAILURE_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10.0  # identity may be waking from sleep
MAX_RESPONSE_BYTES = 64 * 1024
_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
_SCOPE = re.compile(r'[A-Za-z0-9][A-Za-z0-9:._/-]{0,127}( [A-Za-z0-9][A-Za-z0-9:._/-]{0,127}){0,31}')
_TOKEN = re.compile(r'[A-Za-z0-9._~+/=-]{1,8192}')

Post = Callable[[str, bytes, float], tuple[int, bytes]]


class ServiceTokenError(Exception):
    """No usable service token; the message never contains the identity response."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(url: str, form: bytes, timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=form, method='POST', headers={
        'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
    try:
        with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        error.close()
        return error.code, b''


class ServiceTokenSource:
    """``authorization()`` returns ``Bearer <token>`` for one audience, renewing it as needed.

    A token is renewed ``refresh_margin`` seconds (at most half its life) before it expires.
    When renewal fails the current token is used while it is still valid, and the next
    attempt waits ``RETRY_AFTER_FAILURE_SECONDS``; an expired token is never returned.
    Expiry is tracked on ``clock`` (monotonic); ``wall_clock`` only dates the assertion.
    One lock covers renewal, so concurrent callers wait for a single request (at most
    about ``REQUEST_TIMEOUT_SECONDS`` per network step) instead of sending their own.
    """

    def __init__(self, *, token_url: str, client_id: str, private_key_pem: str, audience: str,
                 scope: str | None = None, refresh_margin: int = 60, clock: Callable[[], float] = time.monotonic,
                 wall_clock: Callable[[], float] = time.time, post: Post | None = None):
        parsed = urlparse(token_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('token_url must be an HTTPS URL')
        if not isinstance(client_id, str) or not _NAME.fullmatch(client_id):
            raise ValueError('invalid client_id')
        if not isinstance(audience, str) or not _NAME.fullmatch(audience):
            raise ValueError('invalid audience')
        if scope is not None and (not isinstance(scope, str) or not _SCOPE.fullmatch(scope)):
            raise ValueError('invalid scope')
        if isinstance(refresh_margin, bool) or not isinstance(refresh_margin, int) or not 0 <= refresh_margin <= 3600:
            raise ValueError('refresh_margin must be 0..3600 seconds')
        try:
            key = load_pem_private_key(private_key_pem.replace('\\n', '\n').encode(), password=None)
        except (AttributeError, TypeError, ValueError):
            raise ValueError('private_key_pem must be an unencrypted PEM private key') from None
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError('the client key must be an RSA private key of at least 2048 bits')
        self._token_url, self._client_id, self._audience, self._scope = token_url, client_id, audience, scope
        self._key, self._refresh_margin, self._clock, self._wall_clock = key, refresh_margin, clock, wall_clock
        self._post = post or _post
        self._token: str | None = None
        self._expires_at = self._renew_at = self._retry_at = 0.0
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f'ServiceTokenSource(client_id={self._client_id!r}, audience={self._audience!r})'

    def authorization(self) -> str:
        with self._lock:
            now = self._clock()
            if self._token is not None and now < self._renew_at:
                return 'Bearer ' + self._token
            if now >= self._retry_at:
                try:
                    self._fetch(now)
                except ServiceTokenError:
                    now = self._clock()  # the failed request took time; judge expiry after it
                    self._retry_at = now + RETRY_AFTER_FAILURE_SECONDS
                    if self._token is None or now >= self._expires_at:
                        self._token = None
                        raise
            if self._token is None or now >= self._expires_at:
                self._token = None
                raise ServiceTokenError('no valid service token')
            return 'Bearer ' + self._token

    def _fetch(self, now: float) -> None:
        issued = int(self._wall_clock())
        assertion = jwt.encode({'iss': self._client_id, 'sub': self._client_id, 'aud': self._token_url,
                                'iat': issued, 'exp': issued + ASSERTION_LIFETIME_SECONDS,
                                'jti': str(uuid.uuid4())}, self._key, algorithm='RS256')
        form = {'grant_type': 'client_credentials', 'client_assertion_type': ASSERTION_TYPE,
                'client_assertion': assertion, 'client_id': self._client_id, 'audience': self._audience}
        if self._scope is not None:
            form['scope'] = self._scope
        try:
            status, body = self._post(self._token_url, urlencode(form).encode(), REQUEST_TIMEOUT_SECONDS)
        except (OSError, http.client.HTTPException, RecursionError):
            raise ServiceTokenError('identity is unreachable') from None
        if status != 200:
            raise ServiceTokenError(f'identity refused the token request (HTTP {status})')
        try:
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError()
            data = json.loads(body)
            token, expires_in = data['access_token'], data['expires_in']
            if (data.get('token_type', '').lower() != 'bearer' or not isinstance(token, str)
                    or not _TOKEN.fullmatch(token) or isinstance(expires_in, bool) or not isinstance(expires_in, int)
                    or not 0 < expires_in <= 86400):
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise ServiceTokenError('identity returned an invalid token response') from None
        self._token = token
        self._expires_at = now + expires_in
        self._renew_at = self._expires_at - min(self._refresh_margin, expires_in / 2)
        self._retry_at = 0.0
