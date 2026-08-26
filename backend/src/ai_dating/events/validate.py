from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError
from referencing import Registry
from referencing.jsonschema import DRAFT202012

SCHEMAS_DIR = Path(__file__).parent / "schemas"


class EventValidationError(ValueError):
    pass


def _load(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text())


@cache
def _registry() -> Registry:
    registry = Registry()
    for path in SCHEMAS_DIR.glob("*.json"):
        registry = registry.with_resource(
            path.name, DRAFT202012.create_resource(_load(path.name))
        )
    return registry


def schema_filename(event_name: str, schema_version: int) -> str:
    return f"{event_name}.v{schema_version}.json"


def validate_event(payload: object) -> None:
    if not isinstance(payload, dict):
        raise EventValidationError("event must be an object")
    name = payload.get("event_name")
    version = payload.get("schema_version")
    if not isinstance(name, str) or not isinstance(version, int):
        raise EventValidationError("event_name and schema_version are required")
    path = SCHEMAS_DIR / schema_filename(name, version)
    if not path.is_file():
        raise EventValidationError(f"unknown event schema {name} v{version}")
    schema = _load(path.name)
    validator = Draft202012Validator(
        schema,
        registry=_registry(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    try:
        validator.validate(payload)
    except JsonSchemaError as exc:
        raise EventValidationError(exc.message) from exc
