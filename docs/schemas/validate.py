#!/usr/bin/env python3
"""Validate Yanzhong ecosystem schemas, examples, references, and fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin


ROOT = Path(__file__).resolve().parent
SCHEMA_GLOB = "*.schema.json"


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: invalid JSON: {exc}") from exc


def walk_refs(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and isinstance(child, str):
                yield child
            yield from walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_refs(child)


def structural_checks(schemas: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    ids: dict[str, str] = {}
    known_ids = {schema.get("$id") for schema in schemas.values()}

    for name, schema in schemas.items():
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            errors.append(f"{name}: missing string $id")
            continue
        if schema_id in ids:
            errors.append(f"{name}: duplicate $id also used by {ids[schema_id]}")
        ids[schema_id] = name
        if not schema_id.endswith(f"/{name}"):
            errors.append(f"{name}: $id must end with the exact file name")
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name}: expected JSON Schema Draft 2020-12")

        for ref in walk_refs(schema):
            target, _ = urldefrag(urljoin(schema_id, ref))
            if target and target not in known_ids:
                errors.append(f"{name}: unresolved local schema reference {ref}")

    return errors


def semantic_checks(
    schemas: dict[str, dict[str, object]],
    invalid_fixtures: list[tuple[Path, dict[str, object]]],
) -> tuple[list[str], int, int]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker, ValidationError
        from referencing import Registry, Resource
    except ImportError as exc:
        raise RuntimeError(
            "full validation requires the project/CI jsonschema and referencing packages"
        ) from exc

    registry = Registry().with_resources(
        (str(schema["$id"]), Resource.from_contents(schema))
        for schema in schemas.values()
    )
    validators = {}
    errors: list[str] = []
    valid_count = 0

    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(
                schema,
                registry=registry,
                format_checker=FormatChecker(),
            )
            validators[name] = validator
            for index, example in enumerate(schema.get("examples", []), start=1):
                validator.validate(example)
                valid_count += 1
        except Exception as exc:  # jsonschema exposes several validation subclasses
            errors.append(f"{name}: schema or embedded example is invalid: {exc}")

    rejected_count = 0
    for path, fixture in invalid_fixtures:
        schema_name = fixture.get("schema")
        instance = fixture.get("instance")
        if not isinstance(schema_name, str) or schema_name not in validators:
            errors.append(f"{path.relative_to(ROOT)}: unknown schema {schema_name!r}")
            continue
        try:
            validators[schema_name].validate(instance)
        except ValidationError:
            rejected_count += 1
        else:
            errors.append(f"{path.relative_to(ROOT)}: invalid fixture was accepted")

    return errors, valid_count, rejected_count


def main() -> int:
    schema_paths = sorted(ROOT.glob(SCHEMA_GLOB))
    schemas = {path.name: load_json(path) for path in schema_paths}
    if not all(isinstance(schema, dict) for schema in schemas.values()):
        print("schema roots must be JSON objects", file=sys.stderr)
        return 1

    fixture_paths = sorted((ROOT / "fixtures" / "invalid").glob("*.json"))
    invalid_fixtures = [(path, load_json(path)) for path in fixture_paths]
    errors = structural_checks(schemas)  # type: ignore[arg-type]

    try:
        semantic_errors, valid_count, rejected_count = semantic_checks(
            schemas, invalid_fixtures  # type: ignore[arg-type]
        )
        errors.extend(semantic_errors)
    except RuntimeError as exc:
        print(f"Schema structure OK; semantic validation unavailable: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(
        f"Validated {len(schemas)} schemas, {valid_count} valid examples, "
        f"and {rejected_count} invalid fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
