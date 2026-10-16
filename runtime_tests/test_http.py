import asyncio

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from test_auth import core, keys, claims, token, verifier


class DatabaseFixture:
    def __init__(self):
        self.available = True
        self.closed = False
    def ready(self):
        return self.available
    def close(self):
        self.closed = True


def app_for(keys, **kwargs):
    db = DatabaseFixture()
    app = core().create_app('test-service', db, verifier(keys), **kwargs)
    @app.post('/items')
    async def items(request: Request, principal=Depends(core().require_scope('tasks:write'))):
        return {'workspace':str(principal.workspace), 'size':len(await request.body())}
    @app.get('/fail')
    async def fail():
        raise RuntimeError('SECRET_PAYLOAD')
    @app.get('/slow')
    async def slow():
        await asyncio.sleep(.2)
        return {}
    return app, db


def test_health_readiness_authorization_and_safe_errors(keys):
    app, db = app_for(keys)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get('/healthz').status_code == 200
        assert client.get('/readyz').status_code == 200
        db.available = False
        assert client.get('/readyz').status_code == 503
        assert client.post('/items').status_code == 401
        data = claims()
        data['scope'] = 'tasks:read'
        assert client.post('/items', headers={'Authorization':token(keys,data)}).status_code == 403
        data['scope'] = 'tasks:write'
        result = client.post('/items', headers={'Authorization':token(keys,data), 'X-Workspace-ID':str(__import__('uuid').uuid4()), 'X-Request-ID':'caller-secret'})
        assert result.json()['workspace'] == data['ws']
        assert result.headers['X-Request-ID'] != 'caller-secret'
        response = client.get('/fail')
        assert response.status_code == 500
        assert 'SECRET_PAYLOAD' not in response.text
        metrics = client.get('/metrics').text
        assert 'platform_http_requests_total' in metrics
        assert 'SECRET_PAYLOAD' not in metrics
    assert db.closed


def test_body_and_deadline_bounds(keys):
    app, _ = app_for(keys, max_body_bytes=4, request_timeout=.05)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post('/items',content=b'12345').status_code == 413
        assert client.get('/slow').status_code == 504


def test_chunked_body_limit_and_metric_route_redaction(keys, caplog):
    import logging
    app, _ = app_for(keys, max_body_bytes=4)
    with TestClient(app, raise_server_exceptions=False) as client, caplog.at_level(logging.INFO,logger='platform_backend_core.http'):
        assert client.post('/items',content=iter([b'123',b'45'])).status_code == 413
        assert client.get('/private-customer-payload?token=hidden-token',headers={'Authorization':'Bearer hidden-token'}).status_code == 404
        metrics = client.get('/metrics').text
        assert 'private-customer-payload' not in metrics
        assert 'hidden-token' not in metrics
        assert 'hidden-token' not in caplog.text
        assert 'private-customer-payload' not in caplog.text


def test_validation_errors_do_not_echo_payload(keys):
    from pydantic import BaseModel
    app, _ = app_for(keys)
    class Body(BaseModel):
        count: int
    @app.post('/typed')
    def typed(body: Body):
        return body
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post('/typed',json={'count':'private-sensitive-payload'})
        assert response.status_code == 422
        assert 'private-sensitive-payload' not in response.text


def test_consumer_readiness_checks_fail_closed(keys):
    app, _ = app_for(keys)
    checks = app.state.readiness_checks
    with TestClient(app, raise_server_exceptions=False) as client:
        checks['schema'] = lambda: False
        assert client.get('/readyz').status_code == 503
        checks['schema'] = lambda: True
        assert client.get('/readyz').status_code == 200
        def unavailable():
            raise RuntimeError('private-provider-config')
        checks['provider'] = unavailable
        response = client.get('/readyz')
        assert response.status_code == 503
        assert 'private-provider-config' not in response.text
