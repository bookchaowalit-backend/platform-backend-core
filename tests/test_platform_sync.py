"""Tests for scripts/check_platform_sync.py and the canonical schema pin."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = _load("backend_core_platform_sync", "scripts/check_platform_sync.py")
check = _load("backend_core_check_for_pin", "scripts/check.py")


class CanonicalPinTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name) / "repo"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.pin = self.root / check.PLATFORM_SCHEMA_PIN

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_pin_matches_canonical_schema(self) -> None:
        digest = hashlib.sha256((ROOT / check.PLATFORM_SCHEMA).read_bytes()).hexdigest()
        self.assertTrue((ROOT / check.PLATFORM_SCHEMA_PIN).read_text(encoding="utf-8").startswith(digest + "  "))
        self.assertEqual(check.pin_errors(ROOT), [])

    def test_schema_change_without_pin_update_fails(self) -> None:
        schema = self.root / check.PLATFORM_SCHEMA
        schema.write_bytes(schema.read_bytes() + b"\n")
        self.assertTrue(any("is stale" in error for error in check.validate(self.root)))

    def test_missing_pin_fails(self) -> None:
        self.pin.unlink()
        self.assertIn(f"{check.PLATFORM_SCHEMA_PIN} is missing", check.validate(self.root))

    def test_malformed_pin_fails(self) -> None:
        self.pin.write_text("abc  other.json\n", encoding="utf-8")
        self.assertTrue(any("must contain one" in error for error in check.pin_errors(self.root)))


class PlatformSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp.name)

    def tearDown(self) -> None:
        self._temp.cleanup()

    def platform(self, name: str, pin: bool = True) -> Path:
        repo = self.workspace / name
        (repo / "schema").mkdir(parents=True)
        shutil.copyfile(ROOT / sync.CANONICAL_SCHEMA, repo / sync.VENDORED_SCHEMA)
        if pin:
            shutil.copyfile(ROOT / sync.CANONICAL_PIN, repo / sync.VENDORED_PIN)
        return repo

    def test_matching_platforms_pass(self) -> None:
        self.platform("platform-identity")
        self.platform("platform-api-gateway")
        (self.workspace / "platform-unrelated").mkdir()
        self.assertEqual(sync.compare(ROOT, self.workspace), ([], [], 2))

    def test_drifted_schema_fails(self) -> None:
        repo = self.platform("platform-data")
        (repo / sync.VENDORED_SCHEMA).write_text("{}", encoding="utf-8")
        errors, _, _ = sync.compare(ROOT, self.workspace)
        self.assertEqual(len(errors), 1)
        self.assertIn("platform-data", errors[0])

    def test_stale_pin_fails(self) -> None:
        repo = self.platform("platform-ai")
        (repo / sync.VENDORED_PIN).write_text(f"{'0' * 64}  {sync.SCHEMA_NAME}\n", encoding="utf-8")
        errors, _, _ = sync.compare(ROOT, self.workspace)
        self.assertTrue(any("differs from" in error for error in errors), errors)

    def test_missing_pin_warns_unless_required(self) -> None:
        self.platform("platform-media", pin=False)
        self.assertEqual(len(sync.compare(ROOT, self.workspace)[1]), 1)
        self.assertEqual(len(sync.compare(ROOT, self.workspace, require_pin=True)[0]), 1)

    def test_main_fails_on_empty_workspace(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--workspace", str(self.workspace)]), 1)
            self.platform("platform-payment")
            self.assertEqual(sync.main(["--workspace", str(self.workspace)]), 0)


if __name__ == "__main__":
    unittest.main()
