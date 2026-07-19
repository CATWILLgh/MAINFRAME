#!/usr/bin/env python3
"""Boundary validation tests for bundle publication journals."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

import bundle_publication as publication


TOOLS = Path(__file__).resolve().parent


def _stranded_journal() -> tuple[Path, Path]:
    output = Path(tempfile.mkdtemp(prefix="bundle-journal-")) / "bundle"

    def materialize(staging: Path) -> None:
        (staging / "version").write_text("new")

    with mock.patch.object(
        publication,
        "_commit",
        side_effect=RuntimeError("stop before commit"),
    ):
        try:
            publication.publish_bundle(output, materialize, lambda _: None)
        except RuntimeError as error:
            assert str(error) == "stop before commit"
        else:
            raise AssertionError("publication did not stop before commit")
    journal = output.parent / ".bundle.publication.json"
    assert journal.is_file()
    return output, journal


def _resume(output: Path) -> None:
    publication.publish_bundle(
        output,
        lambda staging: (staging / "version").write_text("final"),
        lambda bundle: (bundle / "version").read_text(),
    )


def _publish_version(output: Path, version: str) -> None:
    def materialize(staging: Path) -> None:
        (staging / "nested").mkdir()
        (staging / "nested/version").write_text(version)

    publication.publish_bundle(
        output,
        materialize,
        lambda bundle: (bundle / "nested/version").read_text(),
    )


def _expect_invalid(output: Path, expected: str) -> None:
    try:
        _resume(output)
    except RuntimeError as error:
        assert expected in str(error).lower(), error
    else:
        raise AssertionError("invalid publication journal was accepted")


def test_oversized_journal_is_rejected_before_decoding() -> None:
    output, journal = _stranded_journal()
    journal.write_bytes(b" " * (1 << 20))
    _expect_invalid(output, "size")


def test_duplicate_journal_keys_are_rejected() -> None:
    output, journal = _stranded_journal()
    payload = journal.read_text()
    journal.write_text(payload.replace('"version":1', '"version":1,"version":1', 1))
    _expect_invalid(output, "duplicate")


def test_insecure_journal_mode_is_rejected() -> None:
    output, journal = _stranded_journal()
    journal.chmod(0o644)
    _expect_invalid(output, "mode")


def test_hardlinked_journal_is_rejected() -> None:
    output, journal = _stranded_journal()
    os.link(journal, journal.with_suffix(".linked"))
    _expect_invalid(output, "link")


def test_replaced_generation_cleanup_never_follows_nested_symlinks() -> None:
    root = Path(tempfile.mkdtemp(prefix="bundle-symlink-cleanup-"))
    output = root / "bundle"
    foreign_directory = root / "foreign-directory"
    foreign_file = root / "foreign-file"
    output.mkdir()
    foreign_directory.mkdir()
    (foreign_directory / "keep").write_text("directory")
    foreign_file.write_text("file")
    (output / "directory-link").symlink_to(foreign_directory, target_is_directory=True)
    (output / "file-link").symlink_to(foreign_file)

    _resume(output)

    assert (foreign_directory / "keep").read_text() == "directory"
    assert foreign_file.read_text() == "file"
    assert not any(path.is_symlink() for path in output.rglob("*"))


def test_symbolic_link_output_parent_is_rejected() -> None:
    root = Path(tempfile.mkdtemp(prefix="bundle-parent-link-"))
    foreign = root / "foreign"
    foreign.mkdir()
    linked_parent = root / "linked-parent"
    linked_parent.symlink_to(foreign, target_is_directory=True)

    try:
        _publish_version(linked_parent / "bundle", "new")
    except (OSError, ValueError):
        pass
    else:
        raise AssertionError("symbolic-link output parent was accepted")
    assert not list(foreign.iterdir())


def test_open_previous_generation_survives_publication_cleanup() -> None:
    output = Path(tempfile.mkdtemp(prefix="bundle-reader-")) / "bundle"
    _publish_version(output, "old")
    old_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        _publish_version(output, "new")
        descriptor = os.open("nested/version", os.O_RDONLY, dir_fd=old_fd)
        try:
            assert os.read(descriptor, 16) == b"old"
        finally:
            os.close(descriptor)
    finally:
        os.close(old_fd)


def test_unjournaled_staging_is_reclaimed_on_next_publish() -> None:
    root = Path(tempfile.mkdtemp(prefix="bundle-orphan-"))
    output = root / "bundle"
    script = textwrap.dedent(
        """
        import os
        import sys
        from pathlib import Path
        from bundle_publication import publish_bundle

        def stop(_):
            os._exit(42)

        publish_bundle(Path(sys.argv[1]), stop, lambda _: None)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(output)],
        env={**os.environ, "PYTHONPATH": str(TOOLS)},
        check=False,
        timeout=10,
    )
    assert result.returncode == 42
    assert list(root.glob(".bundle.staging-*"))

    _publish_version(output, "new")

    assert not list(root.glob(".bundle.staging-*"))


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except Exception as error:
            failures += 1
            print(f"  FAIL {test.__name__}: {error!r}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
