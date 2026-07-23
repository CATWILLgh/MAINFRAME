#!/usr/bin/env python3
"""Strict owned-JSON validation for MAINFRAME release resources."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from release_contract_io import decode_json, read_verified_bytes


MAX_OBSERVED_JSON_SIZE = 1024 * 1024
MAX_OWNED_JSON_POINTERS = 1024
OWNERSHIP_FIELDS = {"kind", "map_pointer", "entry_schema", "registry"}
OWNERSHIP_REGISTRY_FIELDS = {"target", "schema_version", "entries_pointer"}
OWNERSHIP_KIND = "json-map-entry-registry-v1"
OWNERSHIP_ENTRY_SCHEMA = "decision-rule-v1"
DECISIONS = frozenset({"allow", "ask", "deny"})
EXACT_JSON_DOCUMENT_FIELDS = {"schema_version", "events", "feedback"}


def validate_shell_source(source: Path, identifier: str) -> None:
    try:
        content = source.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"resource {identifier!r} source must contain one non-empty logical line"
        ) from exc
    if content.endswith("\n"):
        content = content[:-1]
    unsupported_control = any(
        character != "\t" and unicodedata.category(character) == "Cc"
        for character in content
    )
    if (
        not content.strip(" \t")
        or "\r" in content
        or "\n" in content
        or unsupported_control
    ):
        raise ValueError(
            f"resource {identifier!r} source must contain one non-empty logical line"
        )


def validate_exact_json_document_source(
    root: Path,
    relative: str,
    expected: dict[str, Any],
    identifier: str,
) -> None:
    payload = read_verified_bytes(
        root,
        relative,
        expected,
        max_bytes=MAX_OBSERVED_JSON_SIZE,
    )
    document = decode_json(payload, f"resource {identifier!r} exact JSON source")
    if not isinstance(document, dict) or set(document) != EXACT_JSON_DOCUMENT_FIELDS:
        raise ValueError(
            f"resource {identifier!r} exact JSON source has invalid fields"
        )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != 1
        or type(document["events"]) is not bool
        or type(document["feedback"]) is not bool
    ):
        raise ValueError(
            f"resource {identifier!r} exact JSON source has invalid values"
        )


def validate_owned_json_source(
    root: Path,
    relative: str,
    expected: dict[str, Any],
    resource: dict[str, Any],
    identifier: str,
    *,
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> None:
    has_ownership = "ownership" in resource
    has_owned_pointers = "owned_json_pointers" in resource
    if has_ownership and has_owned_pointers:
        raise ValueError(
            f"resource {identifier!r} ownership conflicts with owned_json_pointers"
        )
    if not has_ownership and not has_owned_pointers:
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers or ownership are required"
        )
    payload = read_verified_bytes(
        root,
        relative,
        expected,
        max_bytes=MAX_OBSERVED_JSON_SIZE,
    )
    document = decode_json(payload, f"resource {identifier!r} JSON source")
    if has_ownership:
        _validate_json_map_ownership(
            document,
            resource,
            identifier,
            parse_location=parse_location,
        )
        return
    pointers = resource["owned_json_pointers"]
    if (
        not isinstance(pointers, list)
        or not pointers
        or len(pointers) > MAX_OWNED_JSON_POINTERS
        or not all(isinstance(pointer, str) for pointer in pointers)
    ):
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers must be non-empty strings"
        )
    if pointers != sorted(set(pointers)):
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers must be sorted and unique"
        )
    token_paths = [json_pointer_tokens(pointer, identifier) for pointer in pointers]
    for index, tokens in enumerate(token_paths):
        if any(token_paths_overlap(tokens, previous) for previous in token_paths[:index]):
            raise ValueError(
                f"resource {identifier!r} owned_json_pointers overlap"
            )
        resolve_object_pointer(document, tokens, identifier)


def _validate_json_map_ownership(
    document: Any,
    resource: dict[str, Any],
    identifier: str,
    *,
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> None:
    label = f"resource {identifier!r} ownership"
    ownership = resource["ownership"]
    _require_exact_object(ownership, OWNERSHIP_FIELDS, label)
    if ownership["kind"] != OWNERSHIP_KIND:
        raise ValueError(f"{label} has unsupported kind")
    if ownership["entry_schema"] != OWNERSHIP_ENTRY_SCHEMA:
        raise ValueError(f"{label} has unsupported entry_schema")
    map_pointer = ownership["map_pointer"]
    map_tokens = _ownership_pointer_tokens(map_pointer, identifier, "map_pointer")
    try:
        source_map = resolve_object_pointer(document, map_tokens, identifier)
    except ValueError as exc:
        raise ValueError(f"{label} map_pointer must resolve through object members") from exc
    if not isinstance(source_map, dict) or not all(
        isinstance(action, str)
        and action
        and _is_decision_rule(rule)
        for action, rule in source_map.items()
    ):
        raise ValueError(f"{label} source map does not match decision-rule-v1")

    registry = ownership["registry"]
    _require_exact_object(registry, OWNERSHIP_REGISTRY_FIELDS, f"{label} registry")
    if (
        type(registry["schema_version"]) is not int
        or registry["schema_version"] != 1
    ):
        raise ValueError(f"{label} registry has unsupported schema_version")
    _ownership_pointer_tokens(
        registry["entries_pointer"],
        identifier,
        "registry entries_pointer",
    )
    if registry["entries_pointer"] != "/actions":
        raise ValueError(f"{label} registry has unsupported entries_pointer")
    target = parse_location(resource["target"], f"{label} resource target")
    registry_target = parse_location(
        registry["target"],
        f"{label} registry target",
    )
    if registry_target[0] != target[0]:
        raise ValueError(f"{label} registry must use the adapter-local target root")


def _require_exact_object(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} must contain exactly {sorted(fields)}")


def _ownership_pointer_tokens(
    pointer: Any,
    identifier: str,
    field: str,
) -> tuple[str, ...]:
    try:
        return json_pointer_tokens(pointer, identifier)
    except ValueError as exc:
        raise ValueError(
            f"resource {identifier!r} ownership {field} must be a non-root RFC 6901 pointer"
        ) from exc


def _is_decision_rule(value: Any) -> bool:
    if isinstance(value, str):
        return value in DECISIONS
    return isinstance(value, dict) and bool(value) and all(
        isinstance(pattern, str)
        and pattern
        and isinstance(decision, str)
        and decision in DECISIONS
        for pattern, decision in value.items()
    )


def json_pointer_tokens(pointer: Any, identifier: str) -> tuple[str, ...]:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers must be non-root RFC 6901 pointers"
        )
    tokens = []
    for encoded in pointer[1:].split("/"):
        tokens.append(_decode_pointer_token(encoded, identifier))
    return tuple(tokens)


def _decode_pointer_token(encoded: str, identifier: str) -> str:
    decoded = []
    index = 0
    while index < len(encoded):
        if encoded[index] != "~":
            decoded.append(encoded[index])
            index += 1
            continue
        if index + 1 == len(encoded) or encoded[index + 1] not in "01":
            raise ValueError(
                f"resource {identifier!r} owned_json_pointers contain invalid RFC 6901 escape"
            )
        decoded.append("~" if encoded[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def resolve_object_pointer(
    document: Any,
    tokens: tuple[str, ...],
    identifier: str,
) -> Any:
    current = document
    for token in tokens:
        if not isinstance(current, dict) or token not in current:
            raise ValueError(
                f"resource {identifier!r} owned_json_pointers must resolve through object members"
            )
        current = current[token]
    return current


def token_paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    common = min(len(left), len(right))
    return left[:common] == right[:common]
