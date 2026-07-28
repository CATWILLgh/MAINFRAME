"""Filesystem and JSON primitives for the release contract."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any


def seal_bundle_payload(root: Path) -> None:
    """Remove write bits before payload modes become part of the manifest."""
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"bundle payload contains symbolic link {path}")
        if path.is_file() and path.relative_to(root).as_posix() != "bundle.json":
            path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)


def seal_release_files(root: Path) -> None:
    """Remove write bits from release metadata files outside bundle payloads."""
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"release contains symbolic link {path}")
        if path.is_file():
            path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)


def payload_inventory(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError(f"bundle payload contains symbolic link {relative!r}")
        if path.is_dir() or relative == "bundle.json":
            continue
        if not path.is_file():
            raise ValueError(f"bundle payload contains non-regular file {relative!r}")
        metadata = path.stat()
        rows.append(
            {
                "path": relative,
                "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
                "size": metadata.st_size,
                "sha256": digest(path),
            }
        )
    return rows


def read_json(path: Path) -> Any:
    return decode_json(path.read_bytes(), path)


def decode_json(payload: bytes, label: Path | str) -> Any:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(constant):
        raise ValueError(f"{label}: invalid JSON constant {constant!r}")

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid JSON: {exc}") from exc
    if _contains_surrogate(value):
        raise ValueError(f"{label}: invalid JSON: surrogate code point")
    return value


def read_verified_bytes(
    root: Path,
    relative: str,
    expected: dict[str, Any],
    *,
    max_bytes: int,
) -> bytes:
    if expected["path"] != relative or expected["size"] > max_bytes:
        raise ValueError(f"payload {relative!r} exceeds verified read contract")
    if root.is_symlink():
        raise ValueError("verified payload root must not be a symbolic link")
    parent = _open_directory_chain(root.resolve(strict=True))
    try:
        parts = PurePosixPath(relative).parts
        for segment in parts[:-1]:
            child = os.open(segment, _directory_flags(), dir_fd=parent)
            os.close(parent)
            parent = child
        descriptor = os.open(parts[-1], _file_flags(), dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"payload {relative!r} must be a regular file")
        payload = stream.read(max_bytes + 1)
    mode = f"{stat.S_IMODE(metadata.st_mode):04o}"
    digest_value = hashlib.sha256(payload).hexdigest()
    if (
        len(payload) > max_bytes
        or len(payload) != expected["size"]
        or mode != expected["mode"]
        or digest_value != expected["sha256"]
    ):
        raise ValueError(f"payload {relative!r} integrity mismatch")
    return payload


def _open_directory_chain(path: Path) -> int:
    if not hasattr(os, "O_NOFOLLOW") or path.anchor != "/":
        raise ValueError("verified payload reads require Unix no-follow support")
    parent = os.open("/", _directory_flags())
    try:
        for segment in path.parts[1:]:
            child = os.open(segment, _directory_flags(), dir_fd=parent)
            os.close(parent)
            parent = child
    except Exception:
        os.close(parent)
        raise
    return parent


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _file_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def _contains_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return any(_contains_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_surrogate(key) or _contains_surrogate(item)
            for key, item in value.items()
        )
    return False


def write_json(path: Path, value: Any) -> None:
    if path.is_symlink():
        path.unlink()
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def portable_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or not value.isascii() or "\\" in value:
        raise ValueError(f"{label} must be a portable relative path")
    path = PurePosixPath(value)
    invalid = path.is_absolute() or value != path.as_posix()
    if invalid or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a portable relative path")
    return value


def real_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be a real directory: {path}")
    return path


def require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")


def relative_inside(root: Path, path: Path, label: str) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must be inside release root") from exc
    portable_path(relative, label)
    reject_symlink_segments(root, relative)
    return relative


def reject_symlink_segments(root: Path, relative: str) -> None:
    current = root
    for segment in PurePosixPath(relative).parts:
        current = current / segment
        if current.is_symlink():
            raise ValueError(f"path contains symbolic link: {relative!r}")
