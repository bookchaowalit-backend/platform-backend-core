# 10 — Sequences

## 1. Authenticated request ใน consumer ที่สร้างด้วย `create_app`

```mermaid
sequenceDiagram
    participant C as Caller
    participant B as _Boundary middleware
    participant R as require_scope dependency
    participant V as TokenVerifier
    participant H as Service handler
    participant D as Database pool
    participant P as PostgreSQL
    C->>B: HTTP request + Authorization
    B->>B: check Content-Length, buffer body up to limit, start deadline
    B->>R: replayed request
    R->>V: verify(authorization)
    V-->>R: Principal(actor, workspace, scopes) or AuthenticationError
    alt invalid token
        R-->>C: 401 unauthorized
    else scope missing
        R-->>C: 403 forbidden
    else ok
        R->>H: principal
        H->>D: transaction(principal.workspace)
        D->>P: check_connection, set_config app.workspace_id local
        P-->>D: rows filtered by RLS
        D-->>H: commit or rollback on exception
        H-->>B: response
        B-->>C: response + X-Request-ID
    end
    B->>B: count route template + status, log correlation_id
```

Sources: src/platform_backend_core/http.py, auth.py, db.py, docs/runtime.md (HTTP integration)

## 2. JWKS key lookup

```mermaid
sequenceDiagram
    participant V as TokenVerifier
    participant J as _JWKS cache
    participant I as Identity JWKS URL
    V->>J: key for header kid
    alt refresh_at passed
        J->>J: refresh_at = now + 60, clear keys
        J->>I: GET (HTTPS, no redirects, 5 s timeout)
        I-->>J: JSON up to 1 MiB, max 64 keys
        J->>J: validate all entries, publish RSA RS256 sig keys atomically
    end
    alt kid known
        J-->>V: public key
        V->>V: jwt.decode RS256 + strict claims
    else unknown kid or failed refresh
        J-->>V: AuthenticationError
    end
```

Sources: src/platform_backend_core/auth.py (`_JWKS`), runtime_tests/test_auth.py

## 3. Service token (client_credentials + private_key_jwt)

```mermaid
sequenceDiagram
    participant S as Consumer worker
    participant T as ServiceTokenSource
    participant I as Identity token_url
    S->>T: authorization()
    T->>T: take lock, check cached token vs renew_at
    alt needs renewal and retry window open
        T->>T: sign RS256 assertion iss=sub=client_id, aud=token_url, 60 s, jti
        T->>I: POST grant_type=client_credentials, client_assertion, audience, scope
        I-->>T: 200 access_token, token_type bearer, expires_in
        T->>T: renew_at = expiry - min(margin, life/2)
    end
    T-->>S: Bearer token or ServiceTokenError
```

Sources: src/platform_backend_core/service_token.py, runtime_tests/test_service_token.py, platform-workflow/src/platform_workflow/cli.py (consumer, sibling repo)

## 4. `platform-migrate`

```mermaid
sequenceDiagram
    participant O as Operator
    participant M as platform-migrate
    participant P as PostgreSQL
    O->>M: DIR --namespace N, DSN from env var
    M->>P: connect (5 s), SET LOCAL statement 30 s, lock 10 s
    M->>P: pg_advisory_xact_lock shared-history, then namespace
    M->>P: CREATE TABLE IF NOT EXISTS platform_schema_migrations
    M->>P: SELECT version, checksum WHERE namespace
    alt drift or backfill
        M-->>O: exit 1, generic message
    else ok
        M->>P: execute pending SQL + INSERT history
        P-->>M: commit
        M-->>O: applied N migrations
    end
```

Sources: src/platform_backend_core/migrations.py

## Open questions

- ไม่มี
