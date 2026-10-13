# platform-backend-core

Starter repository for the `bookchaowalit-backend` organization.

## Purpose

This repository is an intentionally thin baseline for shared backend
conventions, API contracts, services, and workers. It contains no product
features or runtime yet. Its first shared artifact is the canonical Book
Platform repository contract schema in [`contracts/`](contracts/README.md).

## Repository boundary

- **Owner:** `bookchaowalit-backend`
- **Lifecycle:** shared backend foundation
- **Default branch:** `main`
- **Status:** starter / skeleton

## CI

GitHub Actions runs `python3 scripts/check.py` and the unit tests on pushes
and pull requests. The check verifies that the baseline files remain present,
that shared schemas use only the JSON Schema subset the platform repositories
enforce, that `contracts/book-platform.contract.v1.schema.json.sha256` pins
the current schema digest, and that `contracts/examples/valid` passes while
`contracts/examples/invalid` fails.

## Local development

There is no runtime or third-party dependency. With Python 3.11+:

```bash
python3 scripts/check.py
python3 -m unittest discover -s tests -v
# with platform repositories checked out next to this one:
python3 scripts/check_platform_sync.py --workspace ..
```

Add implementation only when a concrete backend product or shared contract is
approved. Planned work is tracked in [`docs/UPGRADE-PLAN.md`](docs/UPGRADE-PLAN.md).

## License

MIT. See [`LICENSE`](./LICENSE).
