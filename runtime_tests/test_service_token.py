"""Service tokens from platform-identity's client_credentials grant (platform-identity docs/SERVICE-CLIENTS.md)."""
import json
import urllib.parse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from platform_backend_core import ServiceTokenError, ServiceTokenSource

TOKEN_URL = 'https://identity.test/v1/token'


def pem(private):
    return private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                 serialization.NoEncryption()).decode()


class FakeIdentity:
    def __init__(self, keys):
        self.public = keys[1]
        self.calls = []
        self.status, self.body = 200, None
        self.expires_in = 600

    def __call__(self, url, form, timeout):
        assert timeout <= 10
        self.calls.append((url, urllib.parse.parse_qs(form.decode())))
        if self.body is not None:
            return self.status, self.body
        return self.status, json.dumps({'access_token': f'token-{len(self.calls)}', 'token_type': 'Bearer',
                                        'expires_in': self.expires_in}).encode()

    def assertion(self, index=-1):
        form = self.calls[index][1]
        # The tests use a fake clock, so time claims are asserted explicitly instead of against now.
        return jwt.decode(form['client_assertion'][0], self.public, algorithms=['RS256'], audience=TOKEN_URL,
                          options={'verify_exp': False, 'verify_iat': False})


@pytest.fixture
def identity(keys):
    return FakeIdentity(keys)


def source(keys, identity, now, **options):
    settings = {'token_url': TOKEN_URL, 'client_id': 'workflow-worker', 'private_key_pem': pem(keys[0]),
                    'audience': 'workflow-api', 'scope': 'jobs:work', 'clock': lambda: now[0], 'post': identity}
    settings.update(options)
    return ServiceTokenSource(**settings)


def test_requests_a_token_with_a_signed_single_use_assertion(keys, identity):
    now = [1000.0]
    tokens = source(keys, identity, now)
    assert tokens.authorization() == 'Bearer token-1'
    url, form = identity.calls[0]
    assert url == TOKEN_URL
    assert form['grant_type'] == ['client_credentials']
    assert form['client_assertion_type'] == ['urn:ietf:params:oauth:client-assertion-type:jwt-bearer']
    assert (form['audience'], form['scope'], form['client_id']) == (['workflow-api'], ['jobs:work'], ['workflow-worker'])
    claims = identity.assertion()
    assert claims['iss'] == claims['sub'] == 'workflow-worker'
    assert claims['aud'] == TOKEN_URL
    assert claims['iat'] == 1000 and 0 < claims['exp'] - claims['iat'] <= 300
    assert claims['jti']


def test_reuses_the_token_until_the_refresh_margin_then_renews(keys, identity):
    now = [1000.0]
    tokens = source(keys, identity, now)
    tokens.authorization()
    now[0] = 1000 + 600 - 61
    assert tokens.authorization() == 'Bearer token-1'
    assert len(identity.calls) == 1
    now[0] = 1000 + 600 - 59
    assert tokens.authorization() == 'Bearer token-2'
    assert identity.assertion(0)['jti'] != identity.assertion(1)['jti']


def test_short_tokens_refresh_at_half_their_life(keys, identity):
    now = [0.0]
    identity.expires_in = 60
    tokens = source(keys, identity, now)
    tokens.authorization()
    now[0] = 29
    tokens.authorization()
    now[0] = 31
    tokens.authorization()
    assert len(identity.calls) == 2


def test_failed_refresh_keeps_a_still_valid_token_and_backs_off(keys, identity):
    now = [0.0]
    tokens = source(keys, identity, now)
    tokens.authorization()
    identity.status, identity.body = 503, b'{"error":"temporarily_unavailable"}'
    now[0] = 560
    assert tokens.authorization() == 'Bearer token-1'
    assert tokens.authorization() == 'Bearer token-1'
    assert len(identity.calls) == 2, 'a failed refresh waits before trying again'
    now[0] = 600
    with pytest.raises(ServiceTokenError):
        tokens.authorization()


@pytest.mark.parametrize('status,body', [
    (401, b'{"error":"invalid_client","error_description":"client authentication failed"}'),
    (200, b'not json'),
    (200, b'{"access_token":"x","token_type":"MAC","expires_in":600}'),
    (200, b'{"token_type":"Bearer","expires_in":600}'),
    (200, b'{"access_token":"x","token_type":"Bearer","expires_in":0}'),
    (200, b'{"access_token":"x","token_type":"Bearer","expires_in":true}'),
    (200, b'{"access_token":"has space","token_type":"Bearer","expires_in":600}'),
    (200, b'[]'),
])
def test_bad_answers_raise_without_echoing_them(keys, identity, status, body):
    identity.status, identity.body = status, body
    with pytest.raises(ServiceTokenError) as caught:
        source(keys, identity, [0.0]).authorization()
    assert 'client authentication failed' not in str(caught.value)
    assert 'has space' not in str(caught.value)


def test_transport_errors_become_service_token_errors(keys):
    def broken(url, form, timeout):
        raise OSError('connection refused')
    with pytest.raises(ServiceTokenError):
        ServiceTokenSource(token_url=TOKEN_URL, client_id='workflow-worker', private_key_pem=pem(keys[0]),
                           audience='workflow-api', post=broken).authorization()


def test_scope_is_optional(keys, identity):
    source(keys, identity, [0.0], scope=None).authorization()
    assert 'scope' not in identity.calls[0][1]


@pytest.mark.parametrize('options', [
    {'token_url': 'http://identity.test/v1/token'},
    {'token_url': 'https://user:pw@identity.test/v1/token'},
    {'client_id': ''},
    {'audience': ''},
    {'scope': 'not\x00ok'},
    {'private_key_pem': 'nope'},
    {'refresh_margin': -1},
])
def test_rejects_bad_configuration(keys, identity, options):
    with pytest.raises(ValueError):
        source(keys, identity, [0.0], **options)


def test_rejects_small_or_non_rsa_keys(keys, identity):
    small = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    with pytest.raises(ValueError):
        source(keys, identity, [0.0], private_key_pem=pem(small))


def test_never_shows_the_key_or_token(keys, identity):
    tokens = source(keys, identity, [0.0])
    tokens.authorization()
    assert 'PRIVATE KEY' not in repr(tokens) and 'token-1' not in repr(tokens)


def test_escaped_newlines_in_the_key_are_accepted(keys, identity):
    escaped = pem(keys[0]).replace('\n', '\\n')
    assert source(keys, identity, [0.0], private_key_pem=escaped).authorization() == 'Bearer token-1'


def test_default_transport_posts_the_form_and_never_follows_redirects():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from platform_backend_core.service_token import _post

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, self.headers['Content-Type'], self.rfile.read(int(self.headers['Content-Length']))))
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', '/v1/token')
                self.end_headers()
                return
            self.send_response(200 if self.path == '/v1/token' else 401)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        assert _post(base + '/v1/token', b'a=1', 5) == (200, b'{"ok":true}')
        assert seen[0] == ('/v1/token', 'application/x-www-form-urlencoded', b'a=1')
        assert _post(base + '/denied', b'a=1', 5) == (401, b'')
        assert _post(base + '/redirect', b'a=1', 5)[0] == 302
        assert [path for path, _, _ in seen] == ['/v1/token', '/denied', '/redirect']
    finally:
        server.shutdown()
