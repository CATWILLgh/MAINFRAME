"""Filesystem and JSON primitives for the release contract."""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path, PurePosixPath
from typing import Any


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
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


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
