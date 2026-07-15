#!/usr/bin/env python3
"""Safely reconcile generated bundle trees without following symlinks."""

from __future__ import annotations

import shutil
from pathlib import Path


def source_files(source: Path) -> dict[Path, Path]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"bundle source must be a real directory: {source}")
    files = {}
    for path in sorted(source.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"bundle source must not be a symlink: {path}")
        if path.is_file() and path.name != ".DS_Store":
            files[path.relative_to(source)] = path
    return files


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            remove_path(child)
        path.rmdir()
    else:
        path.unlink(missing_ok=True)


def copy_regular_file(
    source: Path, destination: Path, *, executable: bool = False
) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"bundle source must be a regular file: {source}")
    if destination.is_symlink() or (
        destination.exists() and not destination.is_file()
    ):
        remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if executable:
        destination.chmod(0o755)


def write_text_file(destination: Path, text: str) -> None:
    if destination.is_symlink() or (
        destination.exists() and not destination.is_file()
    ):
        remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)


def prepare_output_root(output: Path, expected_names: set[str]) -> None:
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"bundle output must be a real directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for child in output.iterdir():
        if child.name not in expected_names:
            remove_path(child)


def sync_tree(source: Path, destination: Path) -> None:
    expected = source_files(source)
    if destination.is_symlink() or (
        destination.exists() and not destination.is_dir()
    ):
        remove_path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(destination.rglob("*"), reverse=True):
        relative = path.relative_to(destination)
        if path.is_symlink() and relative not in expected:
            path.unlink()
        elif path.is_file() and relative not in expected:
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    for relative, source_path in expected.items():
        target = destination / relative
        if target.is_symlink() or (target.exists() and not target.is_file()):
            remove_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
