# 19 — Service dependency map

```mermaid
flowchart TD
    core["platform_backend_core"]
    subgraph Py["Python deps (pyproject.toml)"]
        fa["fastapi >=0.115,<1"]
        pg["psycopg binary,pool >=3.2,<4"]
        jw["PyJWT crypto >=2.9,<3 (cryptography)"]
        te["test: pytest, httpx"]
        dv["dev: mypy 2.4.0, ruff 0.17.1, pytest-cov 7.1.0"]
    end
    subgraph Runtime["Runtime services (configured by consumer)"]
        db[("PostgreSQL >=16")]
        jwks["Identity JWKS (HTTPS)"]
        tok["Identity token endpoint (HTTPS)"]
    end
    subgraph Build["Build / CI"]
        gh["GitHub git+https"]
        ciw["bookchaowalit/platform-ci-workflows v1.1.1"]
        act["actions/checkout v4, setup-python v5"]
    end
    core --> fa & pg & jw
    core -.-> te & dv
    core --> db
    core --> jwks
    core --> tok
    core -. CI .-> ciw & act
    consumers["9 platform services + identity tests"] --> core
    consumers -. install .-> gh
```

Sources: pyproject.toml, uv.lock, .github/workflows/ci.yml, src/platform_backend_core/auth.py, service_token.py, db.py, docs/runtime.md (PostgreSQL >=16), consumer pins (16-deployment.md)

ไม่มี CDN, queue หรือ object store

## Open questions

- ไม่มี
