#!/usr/bin/env python3
"""Compare every platform repository's vendored contract schema with this canonical copy.

Usage: ``python3 scripts/check_platform_sync.py [--workspace DIR] [--require-pin]``

Scans ``DIR`` (default: the parent of this repository) for Book Platform
repositories (``platform-*``) and, for each one
that vendors ``schema/book-platform.contract.v1.schema.json``, fails when the
copy or its ``.sha256`` pin differs from ``contracts/`` here. A repository
without a pin is a warning unless ``--require-pin`` is given. Read-only and
offline; CI does not run it because sibling checkouts are not available there.
Each platform repository enforces its own pin in CI with
``scripts/check_schema_pin.py``.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "book-platform.contract.v1.schema.json"
CANONICAL_SCHEMA = f"contracts/{SCHEMA_NAME}"
CANONICAL_PIN = f"{CANONICAL_SCHEMA}.sha256"
VENDORED_SCHEMA = f"schema/{SCHEMA_NAME}"
VENDORED_PIN = f"{VENDORED_SCHEMA}.sha256"
PLATFORM_GLOBS = ("platform-*",)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def platform_repositories(workspace: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in PLATFORM_GLOBS:
        found.update(path for path in workspace.glob(pattern) if (path / VENDORED_SCHEMA).is_file())
    return sorted(found)


def compare(core: Path, workspace: Path, require_pin: bool = False) -> tuple[list[str], list[str], int]:
    """Return ``(errors, warnings, checked)`` for all platform repositories in ``workspace``."""

    canonical_digest = _sha256(core / CANONICAL_SCHEMA)
    canonical_pin = (core / CANONICAL_PIN).read_bytes()
    errors: list[str] = []
    warnings: list[str] = []
    repositories = platform_repositories(workspace)
    for repo in repositories:
        digest = _sha256(repo / VENDORED_SCHEMA)
        if digest != canonical_digest:
            errors.append(f"{repo.name}: {VENDORED_SCHEMA} sha256 {digest[:12]} != canonical {canonical_digest[:12]}")
        pin = repo / VENDORED_PIN
        if not pin.is_file():
            (errors if require_pin else warnings).append(f"{repo.name}: {VENDORED_PIN} is missing")
        elif pin.read_bytes() != canonical_pin:
            errors.append(f"{repo.name}: {VENDORED_PIN} differs from {CANONICAL_PIN}")
    return errors, warnings, len(repositories)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=str(ROOT.parent), help="directory holding platform checkouts")
    parser.add_argument("--require-pin", action="store_true", help="fail when a platform has no pin file")
    args = parser.parse_args(argv)
    errors, warnings, checked = compare(ROOT, Path(args.workspace).expanduser().resolve(), args.require_pin)
    for message in warnings:
        print(f"WARN: {message}")
    for message in errors:
        print(f"FAIL: {message}")
    if errors:
        return 1
    if checked == 0:
        print(f"FAIL: no platform repositories with {VENDORED_SCHEMA} under {args.workspace}")
        return 1
    print(f"OK: {checked} platform repositor{'y' if checked == 1 else 'ies'} match {CANONICAL_SCHEMA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
