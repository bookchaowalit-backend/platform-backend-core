"""FastAPI lifecycle, workspace authorization, bounded requests and safe diagnostics."""
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import logging
import math
import re
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

from .auth import AuthenticationError, _SCOPE

_LOG = logging.getLogger('platform_backend_core.http')


def require_scope(scope: str):
    if not isinstance(scope, str) or not _SCOPE.fullmatch(scope):
        raise ValueError('a concrete scope is required')

    def dependency(request: Request):
        try:
            principal = request.app.state.verifier.verify(request.headers.get('authorization'))
        except AuthenticationError:
            raise HTTPException(401, 'unauthorized', headers={'WWW-Authenticate':'Bearer'}) from None
        if scope not in principal.scopes:
            raise HTTPException(403, 'forbidden')
        return principal
    return dependency


class _BodyTooLarge(Exception):
    pass


class _Boundary:
    def __init__(self, app, *, max_body_bytes, request_timeout, metrics, lock):
        self.app, self.limit, self.timeout = app, max_body_bytes, request_timeout
        self.metrics, self.lock = metrics, lock

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        started_at, started, status = time.monotonic(), False, 500
        total = 0

        async def wrapped_send(message):
            nonlocal started, status
            if message['type'] == 'http.response.start':
                started = True
                status = message['status']
                message = {**message, 'headers': [*message.get('headers', []), (b'x-request-id', request_id.encode())]}
            await send(message)

        async def execute():
            nonlocal total
            chunks = []
            for key, value in scope.get('headers', []):
                if key.lower() == b'content-length':
                    try:
                        size = int(value)
                        if size < 0:
                            raise ValueError()
                    except ValueError:
                        return await JSONResponse({'detail':'invalid request'},400)(scope, receive, wrapped_send)
                    if size > self.limit:
                        raise _BodyTooLarge()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                total += len(chunk)
                if total > self.limit:
                    raise _BodyTooLarge()
                chunks.append(chunk)
                if not message.get('more_body', False):
                    break
            consumed = False
            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {'type':'http.request', 'body':b''.join(chunks), 'more_body':False}
                return await receive()
            await self.app(scope, replay, wrapped_send)

        try:
            await asyncio.wait_for(execute(), timeout=self.timeout)
        except _BodyTooLarge:
            await JSONResponse({'detail':'request too large'},413)(scope, receive, wrapped_send)
        except TimeoutError:
            if started:
                raise
            await JSONResponse({'detail':'request timeout'},504)(scope, receive, wrapped_send)
        except Exception:
            if started:
                raise
            await JSONResponse({'detail':'internal server error'},500)(scope, receive, wrapped_send)
        finally:
            route = getattr(scope.get('route'), 'path', 'unmatched')
            # Route templates only. No raw paths, query strings, headers or payloads.
            elapsed = time.monotonic() - started_at
            with self.lock:
                self.metrics[(route,status)] += 1
                self.metrics[('duration',0)] += elapsed
            _LOG.info('request route=%s status=%d correlation_id=%s', route, status, request_id)


def create_app(service_name: str, database, verifier, *, max_body_bytes=1048576, request_timeout=30.0) -> FastAPI:
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', service_name):
        raise ValueError('invalid service name')
    if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 16777216:
        raise ValueError('request body bound must be 1..16777216 bytes')
    if not isinstance(request_timeout,(int,float)) or not math.isfinite(request_timeout) or not 0 < request_timeout <= 300:
        raise ValueError('invalid request timeout')

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await run_in_threadpool(database.close)

    app = FastAPI(title=service_name, lifespan=lifespan, debug=False)
    app.state.database, app.state.verifier = database, verifier
    app.state.readiness_checks = {}

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'detail':'invalid request'},422)

    metrics, lock = Counter(), threading.Lock()
    app.add_middleware(_Boundary, max_body_bytes=max_body_bytes, request_timeout=request_timeout, metrics=metrics, lock=lock)

    @app.get('/healthz', include_in_schema=False)
    def healthz():
        return {'status':'ok'}

    @app.get('/readyz', include_in_schema=False)
    def readyz():
        try:
            ready = database.ready() and all(check() is True for check in tuple(app.state.readiness_checks.values()))
        except Exception:
            ready = False
        return JSONResponse({'status':'ready' if ready else 'unavailable'},200 if ready else 503)

    @app.get('/metrics', include_in_schema=False)
    def metric_response():
        with lock:
            rows = list(metrics.items())
        lines = ['# TYPE platform_http_requests_total counter', '# TYPE platform_http_request_duration_seconds_sum counter']
        for (route,status), count in sorted(rows):
            if route == 'duration':
                lines.append(f'platform_http_request_duration_seconds_sum {count}')
            else:
                escaped = route.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')
                lines.append(f'platform_http_requests_total{{route="{escaped}",status="{status}"}} {count}')
        return PlainTextResponse('\n'.join(lines)+'\n', media_type='text/plain; version=0.0.4')

    return app
