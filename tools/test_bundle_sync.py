#!/usr/bin/env python3
"""Safety contracts for standalone files in generated bundles."""

from __future__ import annotations

import tempfile
from pathlib import Path

from bundle_sync import copy_regular_file, sync_tree, write_text_file


def test_copy_rejects_a_symlink_source():
    root = Path(tempfile.mkdtemp())
    real = root / "real.txt"
    source = root / "source.txt"
    real.write_text("foreign")
    source.symlink_to(real)

    try:
        copy_regular_file(source, root / "output.txt")
    except ValueError as exc:
        assert "source must be a regular file" in str(exc)
    else:
        raise AssertionError("symlink source was accepted")


def test_sync_rejects_a_symlink_source_root():
    root = Path(tempfile.mkdtemp())
    real = root / "real"
    source = root / "source"
    real.mkdir()
    (real / "file.txt").write_text("foreign")
    source.symlink_to(real)

    try:
        sync_tree(source, root / "output")
    except ValueError as exc:
        assert "source must be a real directory" in str(exc)
    else:
        raise AssertionError("symlink source root was accepted")


def test_copy_replaces_a_destination_symlink_without_following_it():
    root = Path(tempfile.mkdtemp())
    source = root / "source.txt"
    foreign = root / "foreign.txt"
    destination = root / "output.txt"
    source.write_text("generated")
    foreign.write_text("foreign")
    destination.symlink_to(foreign)

    copy_regular_file(source, destination)

    assert foreign.read_text() == "foreign"
    assert destination.read_text() == "generated"
    assert not destination.is_symlink()


def test_write_replaces_a_destination_symlink_without_following_it():
    root = Path(tempfile.mkdtemp())
    foreign = root / "foreign.txt"
    destination = root / "output.txt"
    foreign.write_text("foreign")
    destination.symlink_to(foreign)

    write_text_file(destination, "generated")

    assert foreign.read_text() == "foreign"
    assert destination.read_text() == "generated"
    assert not destination.is_symlink()


def _run_all():
    failures = 0
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
