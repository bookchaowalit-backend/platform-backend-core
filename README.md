# platform-backend-core

Shared contracts and installable workspace runtime for `bookchaowalit-backend`.

## Purpose

This repository owns the canonical Book Platform repository contract schema
in [`contracts/`](contracts/README.md) and the `platform-backend-core` Python
package: workspace JWT verification, PostgreSQL transaction context, explicit
migrations, HTTP lifecycle and disposable database test support.
See [`docs/runtime.md`](docs/runtime.md) for interfaces and installation.

## Repository boundary

- **Owner:** `bookchaowalit-backend`
- **Lifecycle:** shared backend foundation
- **Default branch:** `main`
- **Status:** shared runtime implemented; production activation is service-owned

## CI

GitHub Actions runs `python3 scripts/check.py` and the unit tests on pushes
and pull requests (`starter-contract`, Python 3.11, standard library only). The
check verifies that the baseline files remain present, that shared schemas use
only the JSON Schema subset the platform repositories enforce, that
`contracts/book-platform.contract.v1.schema.json.sha256` pins the current schema
digest, and that `contracts/examples/valid` passes while
`contracts/examples/invalid` fails. The shared `ci-python.yml` job (Python 3.12)
installs from `uv.lock` with `uv sync --frozen --all-extras`, runs Ruff and
mypy, and runs the whole pytest suite, including the PostgreSQL RLS, migration
and HTTP/auth tests, against a disposable PostgreSQL under a coverage gate.

## Local development

Offline contract checks require only Python 3.11+:

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
# with platform repositories checked out next to this one:
python3 scripts/check_platform_sync.py --workspace ..
```

Runtime development requires Python >=3.12 and `uv sync --frozen --all-extras`
(dependencies are locked in `uv.lock`; `ruff check .` and `mypy` must pass).
Run `python -m pytest`; supply an explicit disposable PostgreSQL admin DSN as
`PLATFORM_TEST_DSN` for real RLS/concurrency tests. Database tests otherwise skip
visibly. Runtime documentation records remaining service and release boundaries.
Earlier plans remain in [`docs/UPGRADE-PLAN.md`](docs/UPGRADE-PLAN.md).

## License

MIT. See [`LICENSE`](./LICENSE).
