#!/usr/bin/env python3
"""Offline check for the shared backend contracts in this repository.

Verifies the starter baseline files, that every schema under ``contracts/``
uses only the JSON Schema subset the Book Platform repositories validate with
(so a schema change here cannot silently stop being enforced downstream), and
that the example contracts under ``contracts/examples`` pass (``valid/``) or
fail (``invalid/``) as expected. No network access and no third-party packages.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE_FILES = ("README.md", "LICENSE", "PRODUCT.md", ".github/workflows/ci.yml")
PLATFORM_SCHEMA = "contracts/book-platform.contract.v1.schema.json"
# Platform repositories vendor this pin next to their schema copy and fail CI
# when their copy stops matching it (scripts/check_schema_pin.py there).
PLATFORM_SCHEMA_PIN = f"{PLATFORM_SCHEMA}.sha256"
SUPPORTED_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "title",
        "description",
        "type",
        "const",
        "enum",
        "pattern",
        "minLength",
        "minItems",
        "uniqueItems",
        "items",
        "required",
        "properties",
        "additionalProperties",
    }
)
JSON_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "number": (int, float),
    "integer": int,
    "null": type(None),
}


def _type_matches(value: Any, expected: str) -> bool:
    python_type = JSON_TYPES[expected]
    if expected in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, python_type)


def _resolve_ref(schema_root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r}")
    node: Any = schema_root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate_schema(value: Any, schema: dict[str, Any], schema_root: dict[str, Any], path: str = "$") -> list[str]:
    """Validate ``value`` with the JSON Schema subset used by the contract schema."""

    if "$ref" in schema:
        return validate_schema(value, _resolve_ref(schema_root, schema["$ref"]), schema_root, path)
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        return [f"{path} must be {schema['const']!r}"]
    if "enum" in schema and value not in schema["enum"]:
        return [f"{path} must be one of {schema['enum']}"]
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(value, expected_type):
        return [f"{path} must be of type {expected_type}"]
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path} must not be empty")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            errors.append(f"{path} does not match pattern {pattern}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path} must contain at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for item in value:
                if item in seen:
                    errors.append(f"{path} contains duplicate item {item!r}")
                seen.append(item)
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                errors.extend(validate_schema(item, item_schema, schema_root, f"{path}[{index}]"))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                errors.append(f"{path}.{key} is not allowed")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_schema(value[key], child_schema, schema_root, f"{path}.{key}"))
    return errors


def unsupported_keywords(schema: Any, path: str = "$") -> list[str]:
    """Return schema locations that use keywords the subset validator ignores."""

    problems: list[str] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in {"properties", "$defs"}:
                if not isinstance(value, dict):
                    problems.append(f"{path}.{key} must be an object")
                    continue
                for name, child in value.items():
                    problems.extend(unsupported_keywords(child, f"{path}.{key}.{name}"))
            elif key not in SUPPORTED_KEYWORDS:
                problems.append(f"{path}.{key} is not supported by the subset validator")
            elif key == "items":
                problems.extend(unsupported_keywords(value, f"{path}.items"))
            elif key == "pattern":
                try:
                    re.compile(value)
                except (re.error, TypeError):
                    problems.append(f"{path}.pattern is not a valid regular expression")
            elif key == "type" and value not in JSON_TYPES:
                problems.append(f"{path}.type {value!r} is not supported")
    return problems


def pin_errors(root: Path) -> list[str]:
    """Return errors when the schema pin file is missing, malformed or stale."""

    schema_path = root / PLATFORM_SCHEMA
    pin_path = root / PLATFORM_SCHEMA_PIN
    if not pin_path.is_file():
        return [f"{PLATFORM_SCHEMA_PIN} is missing"]
    if not schema_path.is_file():
        return []
    expected_name = Path(PLATFORM_SCHEMA).name
    lines = [line for line in pin_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(\S+)\s*", lines[0]) if len(lines) == 1 else None
    if match is None or Path(match.group(2)).name != expected_name:
        return [f"{PLATFORM_SCHEMA_PIN} must contain one '<sha256>  {expected_name}' line"]
    actual = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    if match.group(1) != actual:
        return [
            (
                f"{PLATFORM_SCHEMA_PIN} is stale: schema sha256 is {actual}; update the pin and "
                "re-vendor both files into every platform repository"
            )
        ]
    return []


def validate(root: Path = ROOT) -> list[str]:
    errors = [f"{name} is missing or empty" for name in BASELINE_FILES if not (root / name).is_file() or not (root / name).stat().st_size]
    errors.extend(pin_errors(root))
    schema_path = root / PLATFORM_SCHEMA
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return errors + [f"{PLATFORM_SCHEMA} is not valid JSON: {exc}"]
    schema_problems = unsupported_keywords(schema)
    if schema_problems:
        # Examples cannot be judged against a schema the validator cannot apply.
        return errors + [f"{PLATFORM_SCHEMA}: {problem}" for problem in schema_problems]
    examples = root / "contracts" / "examples"
    valid = sorted((examples / "valid").glob("*.json"))
    invalid = sorted((examples / "invalid").glob("*.json"))
    if not valid or not invalid:
        errors.append("contracts/examples must contain valid/ and invalid/ fixtures")
    for path in valid + invalid:
        label = path.relative_to(root).as_posix()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{label} is not valid JSON: {exc}")
            continue
        problems = validate_schema(document, schema, schema)
        if path.parent.name == "valid" and problems:
            errors.extend(f"{label}: {problem}" for problem in problems)
        if path.parent.name == "invalid" and not problems:
            errors.append(f"{label} is accepted but must be rejected")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]).resolve() if args else ROOT
    errors = validate(root)
    for message in errors:
        print(f"FAIL: {message}")
    if errors:
        return 1
    print("OK: bookchaowalit-backend-core baseline and shared contract schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
