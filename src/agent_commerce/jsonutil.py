"""Small JSON helpers. They fail closed on the wrong shape."""

from __future__ import annotations

import json
from collections.abc import Mapping

from agent_commerce.errors import ValidationError


def dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def loads(text: str) -> object:
    return json.loads(text)


def as_dict(value: object, label: str = "object") -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    out: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(f"{label} has a non-string key")
        out[key] = item
    return out


def as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be a list")
    return list(value)


def as_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def as_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be an integer")
    return value


def optional_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    return as_int(value, label)


def mapping_items(value: Mapping[str, object]) -> dict[str, object]:
    return dict(value)
