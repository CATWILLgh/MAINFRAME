#!/usr/bin/env python3
"""Descriptor-relative cleanup for private bundle generations."""

from __future__ import annotations

import os
import stat


Identity = tuple[int, int]
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


def _owned_directory_identity(
    parent_fd: int, name: str, *, require_private_mode: bool,
) -> Identity:
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.geteuid():
        raise RuntimeError(f"reserved publication tree {name!r} is unsafe")
    if require_private_mode and stat.S_IMODE(metadata.st_mode) != 0o700:
        raise RuntimeError(f"reserved publication tree {name!r} has unsafe mode")
    return _identity_from_stat(metadata)


def _remove_contents(directory_fd: int) -> None:
    for name in os.listdir(directory_fd):
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode):
            child_fd = os.open(name, _OPEN_DIRECTORY | _NOFOLLOW, dir_fd=directory_fd)
            try:
                _remove_contents(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def remove_exact_tree(parent_fd: int, name: str, identity: Identity) -> None:
    if _identity_at(parent_fd, name) != identity:
        raise RuntimeError(f"refusing to remove {name!r}: identity mismatch")
    descriptor = os.open(name, _OPEN_DIRECTORY | _NOFOLLOW, dir_fd=parent_fd)
    try:
        if _identity_from_stat(os.fstat(descriptor)) != identity:
            raise RuntimeError(f"refusing to remove {name!r}: identity changed")
        _remove_contents(descriptor)
    finally:
        os.close(descriptor)
    if _identity_at(parent_fd, name) != identity:
        raise RuntimeError(f"refusing to remove {name!r}: identity changed")
    os.rmdir(name, dir_fd=parent_fd)


def _reserved_names(parent_fd: int, prefix: str) -> list[str]:
    names = []
    for name in os.listdir(parent_fd):
        suffix = name.removeprefix(prefix)
        if (
            name.startswith(prefix)
            and len(suffix) == 32
            and all(character in "0123456789abcdef" for character in suffix)
        ):
            names.append(name)
    return sorted(names)


def reclaim_orphaned_staging(parent_fd: int, output_name: str) -> None:
    prefix = f".{output_name}.staging-"
    for name in _reserved_names(parent_fd, prefix):
        identity = _owned_directory_identity(parent_fd, name, require_private_mode=True)
        remove_exact_tree(parent_fd, name, identity)
    os.fsync(parent_fd)


def reclaim_older_retained(parent_fd: int, output_name: str, keep: str) -> None:
    prefix = f".{output_name}.retained-"
    for name in _reserved_names(parent_fd, prefix):
        if name == keep:
            continue
        identity = _owned_directory_identity(parent_fd, name, require_private_mode=False)
        remove_exact_tree(parent_fd, name, identity)
    os.fsync(parent_fd)
