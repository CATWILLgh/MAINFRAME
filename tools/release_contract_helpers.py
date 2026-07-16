#!/usr/bin/env python3
"""Shared structural validators for release manifests."""
from __future__ import annotations

import re
from typing import Any

from release_contract_io import portable_path

ITEM_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._/-][a-z0-9_]+)*$")
ROOT_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def location(value: Any, label: str) -> tuple[str, str]:
    require_object(value, label)
    require_fields(value, {"root", "path"}, {"root", "path"}, label)
    root = value["root"]
    if not isinstance(root, str) or not ROOT_IDENTIFIER.fullmatch(root):
        raise ValueError(f"{label} has invalid root")
    return root, portable_path(value["path"], label)


def locations_overlap(left: tuple[str, str], right: tuple[str, str]) -> bool:
    if left[0] != right[0]:
        return False
    return (
        left[1] == right[1]
        or left[1].startswith(right[1] + "/")
        or right[1].startswith(left[1] + "/")
    )


def unique_identifier(value: Any, seen: set[str], label: str) -> str:
    if not isinstance(value, str) or not ITEM_IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label} id {value!r}")
    if value in seen:
        raise ValueError(f"duplicate {label} id {value!r}")
    seen.add(value)
    return value


def require_fields(
    value: dict,
    required: set[str],
    allowed: set[str],
    label: str,
) -> None:
    missing = required - value.keys()
    unknown = value.keys() - allowed
    if missing:
        raise ValueError(f"{label} missing fields {sorted(missing)}")
    if unknown:
        raise ValueError(f"{label} has unknown fields {sorted(unknown)}")


def require_object(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")


def sorted_unique_strings(values: Any, pattern: re.Pattern) -> bool:
    return (
        isinstance(values, list)
        and all(isinstance(item, str) and pattern.fullmatch(item) for item in values)
        and values == sorted(set(values))
    )


def sorted_portable_paths(values: Any) -> bool:
    if not isinstance(values, list):
        return False
    try:
        paths = [portable_path(value, "legacy path") for value in values]
    except ValueError:
        return False
    return paths == sorted(set(paths))
