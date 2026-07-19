#!/usr/bin/env python3
"""Crash-recoverable publication of complete directory bundles."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Callable

import bundle_cleanup as _cleanup
from bundle_rename import NativeRename as _NativeRename


Identity = tuple[int, int]
_JOURNAL_VERSION = 1
_MAX_JOURNAL_BYTES = 8192
_OPEN_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _identity_from_stat(metadata: os.stat_result) -> Identity:
    return metadata.st_dev, metadata.st_ino


def _identity_at(parent_fd: int, name: str) -> Identity | None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return _identity_from_stat(metadata)


def _directory_identity(parent_fd: int, name: str) -> Identity | None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"bundle output {name!r} is a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"bundle output {name!r} is not a directory")
    return _identity_from_stat(metadata)


def _open_lock(parent_fd: int, name: str) -> int:
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | _NOFOLLOW
    descriptor = os.open(name, flags, 0o600, dir_fd=parent_fd)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"publication lock {name!r} is not a regular file")
        if metadata.st_uid != os.geteuid() or metadata.st_nlink != 1:
            raise RuntimeError(f"publication lock {name!r} has unsafe ownership")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _fsync_tree(root: Path) -> None:
    for current, _, files in os.walk(root, topdown=False, followlinks=False):
        current_path = Path(current)
        for filename in files:
            path = current_path / filename
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode):
                descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | _NOFOLLOW)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        _fsync_directory(current_path)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, _OPEN_DIRECTORY | _NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _identity_json(identity: Identity | None) -> dict[str, int] | None:
    if identity is None:
        return None
    return {"dev": identity[0], "ino": identity[1]}


def _journal_record(
    parent: Path, parent_identity: Identity, output_name: str,
    output_identity: Identity | None, staging_name: str, staging_identity: Identity,
) -> dict[str, object]:
    return {
        "version": _JOURNAL_VERSION,
        "parent": {
            "path": str(parent), "name": parent.name,
            "dev": parent_identity[0], "ino": parent_identity[1],
        },
        "output": {"name": output_name, "identity": _identity_json(output_identity)},
        "staging": {"name": staging_name, "identity": _identity_json(staging_identity)},
    }


def _publish_journal(parent_fd: int, journal_name: str, record: dict[str, object]) -> None:
    temporary = f"{journal_name}.tmp-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
            0o600, dir_fd=parent_fd,
        )
        try:
            os.fchmod(descriptor, 0o600)
            payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _NativeRename().no_replace(parent_fd, temporary, journal_name)
        os.fsync(parent_fd)
    except BaseException:
        try:
            os.unlink(temporary, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"publication journal has duplicate key {key!r}")
        result[key] = value
    return result


def _read_journal(parent_fd: int, journal_name: str) -> dict[str, object] | None:
    try:
        descriptor = os.open(journal_name, os.O_RDONLY | os.O_CLOEXEC | _NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("publication journal is not a regular file")
        if metadata.st_uid != os.geteuid():
            raise RuntimeError("publication journal owner is invalid")
        if metadata.st_nlink != 1:
            raise RuntimeError("publication journal link count is invalid")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise RuntimeError("publication journal mode is invalid")
        if metadata.st_size > _MAX_JOURNAL_BYTES:
            raise RuntimeError("publication journal size exceeds the limit")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read(_MAX_JOURNAL_BYTES + 1)
        if len(payload) > _MAX_JOURNAL_BYTES:
            raise RuntimeError("publication journal size exceeds the limit")
        record = json.loads(payload, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError("publication journal is invalid") from error
    finally:
        os.close(descriptor)
    if not isinstance(record, dict):
        raise RuntimeError("publication journal is invalid")
    return record


def _parse_identity(value: object, *, optional: bool = False) -> Identity | None:
    if value is None and optional:
        return None
    if not isinstance(value, dict) or set(value) != {"dev", "ino"}:
        raise RuntimeError("publication journal identity is invalid")
    device, inode = value["dev"], value["ino"]
    if not isinstance(device, int) or not isinstance(inode, int):
        raise RuntimeError("publication journal identity is invalid")
    return device, inode


def _validated_record(
    record: dict[str, object], parent: Path, parent_identity: Identity, output_name: str,
) -> tuple[Identity | None, str, Identity]:
    try:
        parent_data = record["parent"]
        output_data = record["output"]
        staging_data = record["staging"]
        valid_top = set(record) == {"version", "parent", "output", "staging"}
        valid_parent = isinstance(parent_data, dict) and parent_data == {
            "path": str(parent), "name": parent.name,
            "dev": parent_identity[0], "ino": parent_identity[1],
        }
        valid_output = (
            isinstance(output_data, dict)
            and set(output_data) == {"name", "identity"}
            and output_data.get("name") == output_name
        )
        valid_staging = isinstance(staging_data, dict) and set(staging_data) == {
            "name", "identity",
        }
        staging_name = staging_data["name"] if isinstance(staging_data, dict) else None
    except (KeyError, TypeError):
        raise RuntimeError("publication journal is invalid") from None
    prefix = f".{output_name}.staging-"
    if not valid_top or record["version"] != _JOURNAL_VERSION or not valid_parent:
        raise RuntimeError("publication journal does not match its parent")
    if not valid_output or not valid_staging or not isinstance(staging_name, str):
        raise RuntimeError("publication journal names are invalid")
    suffix = staging_name.removeprefix(prefix)
    if (
        Path(staging_name).name != staging_name
        or not staging_name.startswith(prefix)
        or len(suffix) != 32
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise RuntimeError("publication journal staging name is invalid")
    old_identity = _parse_identity(output_data.get("identity"), optional=True)
    new_identity = _parse_identity(staging_data.get("identity"))
    if new_identity is None:
        raise RuntimeError("publication journal staging identity is invalid")
    return old_identity, staging_name, new_identity


def _clear_journal(parent_fd: int, journal_name: str) -> None:
    os.unlink(journal_name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _retained_name(output_name: str, staging_name: str) -> str:
    suffix = staging_name.removeprefix(f".{output_name}.staging-")
    return f".{output_name}.retained-{suffix}"


def _recover(
    parent_fd: int, parent: Path, output_name: str, journal_name: str,
    record: dict[str, object], validate: Callable[[Path], None],
) -> None:
    parent_identity = _identity_from_stat(os.fstat(parent_fd))
    old, staging_name, new = _validated_record(record, parent, parent_identity, output_name)
    retained_name = _retained_name(output_name, staging_name)
    output_now = _identity_at(parent_fd, output_name)
    staging_now = _identity_at(parent_fd, staging_name)
    retained_now = _identity_at(parent_fd, retained_name)
    precommit = output_now == old and staging_now == new and retained_now is None
    aborted = output_now == old and staging_now is None and retained_now is None
    postcommit = (
        output_now == new and staging_now == old and retained_now is None and old is not None
    )
    postretained = (
        output_now == new and staging_now is None and retained_now == old and old is not None
    )
    first_publish = output_now == new and staging_now is None and retained_now is None and old is None
    if precommit:
        _cleanup.remove_exact_tree(parent_fd, staging_name, new)
        os.fsync(parent_fd)
        _clear_journal(parent_fd, journal_name)
        return
    if aborted:
        os.fsync(parent_fd)
        _clear_journal(parent_fd, journal_name)
        return
    if not postcommit and not postretained and not first_publish:
        raise RuntimeError("publication journal identity state is unknown")
    validate(parent / output_name)
    if _identity_at(parent_fd, output_name) != new:
        raise RuntimeError("active bundle identity changed during validation")
    if postcommit:
        if _identity_at(parent_fd, staging_name) != old:
            raise RuntimeError("retained bundle identity changed during validation")
        _NativeRename().no_replace(parent_fd, staging_name, retained_name)
        os.fsync(parent_fd)
    if old is not None:
        if _identity_at(parent_fd, retained_name) != old:
            raise RuntimeError("retained bundle identity changed after publication")
        _cleanup.reclaim_older_retained(parent_fd, output_name, retained_name)
    os.fsync(parent_fd)
    _clear_journal(parent_fd, journal_name)


def _commit(parent_fd: int, output_name: str, staging_name: str, had_output: bool) -> None:
    native = _NativeRename()
    if had_output:
        native.exchange(parent_fd, staging_name, output_name)
    else:
        native.no_replace(parent_fd, staging_name, output_name)


def _create_staging(parent_fd: int, output_name: str) -> tuple[str, Identity]:
    name = f".{output_name}.staging-{uuid.uuid4().hex}"
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    descriptor = os.open(name, _OPEN_DIRECTORY | _NOFOLLOW, dir_fd=parent_fd)
    try:
        os.fchmod(descriptor, 0o700)
        identity = _identity_from_stat(os.fstat(descriptor))
    finally:
        os.close(descriptor)
    return name, identity


def _discard_unjournaled(parent_fd: int, name: str, identity: Identity) -> None:
    _cleanup.remove_exact_tree(parent_fd, name, identity)
    os.fsync(parent_fd)


def _publish_locked(
    parent_fd: int, parent: Path, output_name: str,
    materialize: Callable[[Path], None], validate: Callable[[Path], None],
) -> None:
    journal_name = f".{output_name}.publication.json"
    existing = _read_journal(parent_fd, journal_name)
    if existing is not None:
        _recover(parent_fd, parent, output_name, journal_name, existing, validate)
    _cleanup.reclaim_orphaned_staging(parent_fd, output_name)
    old_identity = _directory_identity(parent_fd, output_name)
    staging_name, staging_identity = _create_staging(parent_fd, output_name)
    staging_path = parent / staging_name
    try:
        materialize(staging_path)
        if _directory_identity(parent_fd, staging_name) != staging_identity:
            raise RuntimeError("staging bundle identity changed during materialization")
        validate(staging_path)
        os.chmod(staging_path, 0o700, follow_symlinks=False)
        _fsync_tree(staging_path)
    except BaseException:
        _discard_unjournaled(parent_fd, staging_name, staging_identity)
        raise
    parent_identity = _identity_from_stat(os.fstat(parent_fd))
    record = _journal_record(
        parent, parent_identity, output_name, old_identity, staging_name, staging_identity,
    )
    _publish_journal(parent_fd, journal_name, record)
    _commit(parent_fd, output_name, staging_name, old_identity is not None)
    os.fsync(parent_fd)
    current = _read_journal(parent_fd, journal_name)
    if current is None:
        raise RuntimeError("publication journal disappeared after commit")
    _recover(parent_fd, parent, output_name, journal_name, current, validate)


def publish_bundle(
    output: Path, materialize: Callable[[Path], None], validate: Callable[[Path], None],
) -> None:
    """Publish a validated directory tree with one native namespace operation.

    The validator must express generation-independent bundle invariants because
    interrupted cleanup validates the already-active generation before deleting it.
    """
    output = Path(output)
    if output.name in {"", ".", ".."}:
        raise ValueError("bundle output must name a child of an existing parent")
    output = Path(os.path.abspath(output))
    parent = output.parent
    _NativeRename()
    parent_fd = os.open(parent, _OPEN_DIRECTORY | _NOFOLLOW)
    lock_fd = -1
    try:
        lock_fd = _open_lock(parent_fd, f".{output.name}.publication.lock")
        _directory_identity(parent_fd, output.name)
        _publish_locked(parent_fd, parent, output.name, materialize, validate)
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        os.close(parent_fd)
