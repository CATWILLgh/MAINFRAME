#!/usr/bin/env python3
"""Strict owned-JSON validation for MAINFRAME release resources."""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from release_contract_io import decode_json, read_verified_bytes


MAX_OBSERVED_JSON_SIZE = 1024 * 1024
MAX_OWNED_JSON_POINTERS = 1024


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


def validate_owned_json_source(
    root: Path,
    relative: str,
    expected: dict[str, Any],
    resource: dict[str, Any],
    identifier: str,
) -> None:
    if "owned_json_pointers" not in resource:
        raise ValueError(
            f"resource {identifier!r} owned_json_pointers are required"
        )
    payload = read_verified_bytes(
        root,
        relative,
        expected,
        max_bytes=MAX_OBSERVED_JSON_SIZE,
    )
    document = decode_json(payload, f"resource {identifier!r} JSON source")
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
) -> None:
    current = document
    for token in tokens:
        if not isinstance(current, dict) or token not in current:
            raise ValueError(
                f"resource {identifier!r} owned_json_pointers must resolve through object members"
            )
        current = current[token]


def token_paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    common = min(len(left), len(right))
    return left[:common] == right[:common]
