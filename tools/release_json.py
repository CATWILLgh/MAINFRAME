#!/usr/bin/env python3
"""Strict owned-JSON validation for MAINFRAME release resources."""

from __future__ import annotations

import unicodedata
import re
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
JSON_CLAIM_OWNERSHIP_FIELDS = {"kind", "registry", "claims"}
JSON_CLAIM_REGISTRY_FIELDS = {"target", "schema_version"}
JSON_CLAIM_COMMON_FIELDS = {"id", "kind", "pointer"}
JSON_ARRAY_CLAIM_FIELDS = JSON_CLAIM_COMMON_FIELDS | {"selector"}
JSON_SELECTOR_FIELDS = {"pointer", "value"}
JSON_CLAIM_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$")


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
    has_claim_ownership = "json_ownership" in resource
    if has_claim_ownership and (has_ownership or has_owned_pointers):
        raise ValueError(f"resource {identifier!r} has conflicting JSON ownership")
    if has_ownership and has_owned_pointers:
        raise ValueError(
            f"resource {identifier!r} ownership conflicts with owned_json_pointers"
        )
    if not has_ownership and not has_owned_pointers and not has_claim_ownership:
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
    if has_claim_ownership:
        _validate_json_claim_source(document, resource["json_ownership"], identifier)
        return
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


def validate_json_claim_ownership(
    ownership: Any,
    resource_target: Any,
    identifier: str,
    *,
    parse_location: Callable[[Any, str], tuple[str, str]],
) -> None:
    label = f"resource {identifier!r} JSON ownership"
    _require_exact_object(ownership, JSON_CLAIM_OWNERSHIP_FIELDS, label)
    if ownership["kind"] != "json-claim-registry-v1":
        raise ValueError(f"{label} has unsupported kind")
    registry = ownership["registry"]
    _require_exact_object(registry, JSON_CLAIM_REGISTRY_FIELDS, f"{label} registry")
    if type(registry["schema_version"]) is not int or registry["schema_version"] != 1:
        raise ValueError(f"{label} registry has unsupported schema_version")
    target = parse_location(resource_target, f"{label} resource target")
    registry_target = parse_location(registry["target"], f"{label} registry target")
    if registry_target[0] != target[0] or _locations_overlap(target, registry_target):
        raise ValueError(f"{label} registry must be adapter-local and non-overlapping")
    claims = ownership["claims"]
    if (
        not isinstance(claims, list)
        or not claims
        or len(claims) > MAX_OWNED_JSON_POINTERS
    ):
        raise ValueError(f"{label} claims must be non-empty")
    identifiers = []
    pointers: list[tuple[str, ...]] = []
    for claim in claims:
        _validate_json_claim(claim, identifier)
        identifiers.append(claim["id"])
        tokens = json_pointer_tokens(claim["pointer"], identifier)
        if any(token_paths_overlap(tokens, previous) for previous in pointers):
            raise ValueError(f"{label} claims overlap")
        pointers.append(tokens)
    if identifiers != sorted(set(identifiers)):
        raise ValueError(f"{label} claims must be sorted and unique")


def _validate_json_claim(claim: Any, identifier: str) -> None:
    if not isinstance(claim, dict):
        raise ValueError(f"resource {identifier!r} JSON ownership claim must be an object")
    kind = claim.get("kind")
    fields = JSON_CLAIM_COMMON_FIELDS if kind == "exact-scalar" else JSON_ARRAY_CLAIM_FIELDS
    _require_exact_object(claim, fields, f"resource {identifier!r} JSON ownership claim")
    if not isinstance(claim["id"], str) or not JSON_CLAIM_ID.fullmatch(claim["id"]):
        raise ValueError(f"resource {identifier!r} JSON ownership claim has invalid id")
    _ownership_pointer_tokens(claim["pointer"], identifier, "claim pointer")
    if kind == "array-entry":
        selector = claim["selector"]
        _require_exact_object(selector, JSON_SELECTOR_FIELDS, f"resource {identifier!r} selector")
        _ownership_pointer_tokens(selector["pointer"], identifier, "selector pointer")
    elif kind != "exact-scalar":
        raise ValueError(f"resource {identifier!r} JSON ownership claim has unsupported kind")


def _validate_json_claim_source(document: Any, ownership: dict[str, Any], identifier: str) -> None:
    for claim in ownership["claims"]:
        tokens = json_pointer_tokens(claim["pointer"], identifier)
        value = resolve_object_pointer(document, tokens, identifier)
        if claim["kind"] == "exact-scalar":
            if isinstance(value, (dict, list)):
                raise ValueError(f"resource {identifier!r} exact scalar claim selects a container")
            continue
        if not isinstance(value, list):
            raise ValueError(f"resource {identifier!r} array claim does not select an array")
        matches = [entry for entry in value if _selector_matches(entry, claim["selector"], identifier)]
        if len(matches) != 1:
            raise ValueError(f"resource {identifier!r} array claim must select exactly one source entry")


def _resolve_pointer(document: Any, raw: str, identifier: str) -> Any:
    current = document
    for token in json_pointer_tokens(raw, identifier):
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise ValueError(f"resource {identifier!r} JSON ownership pointer is unresolved")
    return current


def _selector_matches(entry: Any, selector: dict[str, Any], identifier: str) -> bool:
    try:
        return _resolve_pointer(entry, selector["pointer"], identifier) == selector["value"]
    except ValueError:
        return False


def _locations_overlap(left: tuple[str, str], right: tuple[str, str]) -> bool:
    return left[0] == right[0] and (
        left[1] == right[1]
        or left[1].startswith(right[1] + "/")
        or right[1].startswith(left[1] + "/")
    )


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
