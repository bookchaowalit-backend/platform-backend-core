import importlib.util
import time
from dataclasses import FrozenInstanceError
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def core():
    assert importlib.util.find_spec('platform_backend_core') is not None, 'installable workspace runtime is missing'
    import platform_backend_core
    return platform_backend_core


@pytest.fixture(scope='module')
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def claims():
    now = int(time.time())
    return dict(iss='https://issuer.test', aud='tasks', sub=str(uuid4()), ws=str(uuid4()), iat=now, exp=now+300, jti=str(uuid4()), scope='tasks:read tasks:write')


def verifier(keys):
    return core().TokenVerifier(issuer='https://issuer.test', audience='tasks', public_key=keys[1])


def token(keys, data):
    return 'Bearer ' + jwt.encode(data, keys[0], algorithm='RS256')


def test_valid_workspace_principal_is_immutable(keys):
    data = claims()
    principal = verifier(keys).verify(token(keys, data))
    assert str(principal.workspace) == data['ws']
    assert str(principal.actor) == data['sub']
    assert principal.scopes == frozenset({'tasks:read', 'tasks:write'})
    assert principal.channel == 'api'
    with pytest.raises(FrozenInstanceError):
        principal.channel = 'other'


@pytest.mark.parametrize('field,value', [('iss','wrong'),('aud','wrong'),('sub','owner'),('ws','owner'),('iat',True),('iat',float('nan')),('exp',float('inf')),('exp',0),('exp',999999999999),('jti',''),('scope','*'),('scope','tasks:*'),('scope',['tasks:read']),('scope', 'tasks:read  tasks:write')])
def test_invalid_claims_fail_closed(keys, field, value):
    data = claims()
    data[field] = value
    with pytest.raises(core().AuthenticationError):
        verifier(keys).verify(token(keys, data))


@pytest.mark.parametrize('field', ['sub','ws','iat','exp','jti','iss','aud'])
def test_required_claims(keys, field):
    data = claims()
    del data[field]
    with pytest.raises(core().AuthenticationError):
        verifier(keys).verify(token(keys, data))


def test_wrong_algorithm_and_missing_auth_denied(keys):
    instance = verifier(keys)
    for value in [None, '', 'Basic abc', 'Bearer no', 'Bearer '+jwt.encode(claims(), 'x'*32, algorithm='HS256')]:
        with pytest.raises(core().AuthenticationError):
            instance.verify(value)


def test_explicit_configuration_and_no_implicit_permissions(keys):
    with pytest.raises(ValueError):
        core().TokenVerifier(issuer='https://issuer.test', audience='tasks')
    data = claims()
    del data['scope']
    assert verifier(keys).verify(token(keys, data)).scopes == frozenset()
    source = core().TokenVerifier(issuer='https://issuer.test', audience='tasks', key_source=lambda header: keys[1])
    assert source.verify(token(keys, data)).workspace


@pytest.mark.parametrize('field,value', [('iat',-1),('iat',9999999999),('exp',True),('nbf',float('nan')),('nbf',9999999999),('ws',None),('sub',123),('aud',['tasks']),('scope',' tasks:read'),('jti','has whitespace')])
def test_additional_strict_claims(keys, field, value):
    data = claims()
    data[field] = value
    with pytest.raises(core().AuthenticationError):
        verifier(keys).verify(token(keys,data))


def test_jwks_requires_https_and_refresh_is_bounded(keys, monkeypatch):
    from platform_backend_core import auth
    import io
    import json
    with pytest.raises(ValueError):
        auth.TokenVerifier(issuer='https://issuer.test',audience='tasks',jwks_url='http://key.test/jwks')
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(keys[0].public_key()))
    key.update(kid='test-key', alg='RS256', use='sig')
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, timeout))
            return io.BytesIO(json.dumps({'keys':[key]}).encode())
    monkeypatch.setattr(auth, 'build_opener', lambda handler:Opener())
    instance = auth.TokenVerifier(issuer='https://issuer.test',audience='tasks',jwks_url='https://key.test/jwks')
    signed = 'Bearer '+jwt.encode(claims(),keys[0],algorithm='RS256',headers={'kid':'test-key'})
    assert instance.verify(signed).workspace
    assert instance.verify(signed).workspace
    for i in range(3):
        unknown = 'Bearer '+jwt.encode(claims(),keys[0],algorithm='RS256',headers={'kid':'unknown'})
        with pytest.raises(auth.AuthenticationError):
            instance.verify(unknown)
    assert calls == [('https://key.test/jwks',5)]


@pytest.mark.parametrize('invalid_tail', ['duplicate', 'malformed', 'invalid-kid'])
def test_jwks_rejects_entire_failed_refresh_until_valid_refresh(keys, monkeypatch, invalid_tail):
    from platform_backend_core import auth
    import io
    import json
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(keys[0].public_key()))
    key.update(kid='test-key', alg='RS256', use='sig')
    tail = {'duplicate':key, 'malformed':42, 'invalid-kid':{**key,'kid':''}}[invalid_tail]
    response_keys = [key, tail]
    clock = [100.0]
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return io.BytesIO(json.dumps({'keys':response_keys}).encode())
    monkeypatch.setattr(auth, 'build_opener', lambda handler:Opener())
    monkeypatch.setattr(auth.time, 'monotonic', lambda:clock[0])
    instance = auth.TokenVerifier(issuer='https://issuer.test',audience='tasks',jwks_url='https://key.test/jwks')
    signed = 'Bearer '+jwt.encode(claims(),keys[0],algorithm='RS256',headers={'kid':'test-key'})
    for _ in range(3):
        with pytest.raises(auth.AuthenticationError):
            instance.verify(signed)
    assert len(calls) == 1
    response_keys[:] = [key]
    clock[0] += 61
    assert instance.verify(signed).workspace
    assert len(calls) == 2


@pytest.mark.parametrize('delegation_claims', [
    {'del':str(uuid4()),'obo':str(uuid4())},
    {'del':str(uuid4())},
    {'obo':str(uuid4())},
    {'del':None},
    {'obo':None},
    {'del':None,'obo':None},
])
def test_unsupported_delegation_claims_are_rejected_even_when_null(keys, delegation_claims):
    data = {**claims(),**delegation_claims}
    with pytest.raises(core().AuthenticationError,match='invalid credentials'):
        verifier(keys).verify(token(keys,data))
