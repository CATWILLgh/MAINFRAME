#!/usr/bin/env python3
"""Hermetic tests for atomic direct-bundle publication."""

from __future__ import annotations

import errno
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import bundle_publication as publication


def _root() -> Path:
    return Path(tempfile.mkdtemp(prefix="bundle-publication-"))


def _materialize(value: str):
    def materialize(staging: Path) -> None:
        (staging / "nested").mkdir()
        (staging / "nested/version").write_text(value)

    return materialize


def _validate(expected: str):
    def validate(bundle: Path) -> None:
        assert (bundle / "nested/version").read_text() == expected

    return validate


def _version(output: Path) -> str:
    return (output / "nested/version").read_text()


def _publish(output: Path, value: str) -> None:
    publication.publish_bundle(output, _materialize(value), _validate(value))


def _publish_after_recovery(output: Path, recovered: str, value: str) -> None:
    def validate(bundle: Path) -> None:
        assert _version(bundle) in {recovered, value}

    publication.publish_bundle(output, _materialize(value), validate)


def _journal(output: Path) -> Path:
    return output.parent / f".{output.name}.publication.json"


def _staging_names(output: Path) -> list[Path]:
    prefix = f".{output.name}.staging-"
    return [path for path in output.parent.iterdir() if path.name.startswith(prefix)]


def _retained_names(output: Path) -> list[Path]:
    prefix = f".{output.name}.retained-"
    return [path for path in output.parent.iterdir() if path.name.startswith(prefix)]


def test_old_output_survives_materialize_and_validation_failure() -> None:
    for failure in ("materialize", "validate"):
        output = _root() / "bundle"
        _publish(output, "old")

        def materialize(staging: Path) -> None:
            _materialize("new")(staging)
            if failure == "materialize":
                raise RuntimeError("materialize failed")

        def validate(staging: Path) -> None:
            if failure == "validate":
                raise RuntimeError("validate failed")

        try:
            publication.publish_bundle(output, materialize, validate)
        except RuntimeError:
            pass
        else:
            raise AssertionError("publication failure was not propagated")
        assert _version(output) == "old"


def test_first_publish_uses_no_replace() -> None:
    output = _root() / "bundle"
    _publish(output, "first")
    assert _version(output) == "first"
    assert not _journal(output).exists()
    assert not _staging_names(output)


def test_exchange_publish_retains_only_new_output() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    _publish(output, "new")
    assert _version(output) == "new"
    assert not _journal(output).exists()
    assert not _staging_names(output)


def _interrupt_script(output: Path, phase: str) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(
        """
        import os
        import sys
        from pathlib import Path
        import bundle_publication as bp

        output = Path(sys.argv[1])
        phase = sys.argv[2]
        original = bp._commit
        original_clear = bp._clear_journal
        def interrupt(parent_fd, output_name, staging_name, had_output):
            if phase == "before":
                os._exit(42)
            original(parent_fd, output_name, staging_name, had_output)
            if phase == "after":
                os._exit(43)
        def interrupt_clear(parent_fd, journal_name):
            if phase == "after-cleanup":
                os._exit(44)
            original_clear(parent_fd, journal_name)
        bp._commit = interrupt
        bp._clear_journal = interrupt_clear
        def materialize(staging):
            (staging / "nested").mkdir()
            (staging / "nested/version").write_text("new")
        def validate(bundle):
            assert (bundle / "nested/version").read_text() in {"new", "old"}
        bp.publish_bundle(output, materialize, validate)
        """
    )
    env = dict(os.environ, PYTHONPATH=str(TOOLS))
    return subprocess.run(
        [sys.executable, "-c", script, str(output), phase], env=env,
        text=True, capture_output=True, timeout=10,
    )


def test_journal_recovery_before_exchange() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    assert _interrupt_script(output, "before").returncode == 42
    assert _version(output) == "old"
    assert _journal(output).exists() and _staging_names(output)
    assert stat_mode(_journal(output)) == 0o600
    assert stat_mode(_staging_names(output)[0]) == 0o700
    _publish_after_recovery(output, "new", "final")
    assert _version(output) == "final"
    assert not _journal(output).exists() and not _staging_names(output)


def test_journal_recovery_after_exchange() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    assert _interrupt_script(output, "after").returncode == 43
    assert _version(output) == "new"
    assert _journal(output).exists() and _staging_names(output)
    _publish_after_recovery(output, "new", "final")
    assert _version(output) == "final"
    assert not _journal(output).exists() and not _staging_names(output)


def test_journal_recovery_for_first_publish_and_completed_cleanup() -> None:
    for phase, returncode in (("before", 42), ("after", 43)):
        output = _root() / "bundle"
        assert _interrupt_script(output, phase).returncode == returncode
        assert _journal(output).exists()
        _publish_after_recovery(output, "new", "final")
        assert _version(output) == "final"
    output = _root() / "bundle"
    _publish(output, "old")
    assert _interrupt_script(output, "after-cleanup").returncode == 44
    assert _version(output) == "new"
    assert _journal(output).exists() and not _staging_names(output)
    _publish_after_recovery(output, "new", "final")
    assert _version(output) == "final"


def test_journal_recovery_after_precommit_cleanup() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    assert _interrupt_script(output, "before").returncode == 42
    assert _interrupt_script(output, "after-cleanup").returncode == 44
    assert _version(output) == "old"
    assert _journal(output).exists() and not _staging_names(output)
    _publish(output, "final")
    assert _version(output) == "final"


def test_mismatched_identity_fails_closed() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    assert _interrupt_script(output, "before").returncode == 42
    retained_journal = _journal(output).read_bytes()
    staging = _staging_names(output)[0]
    displaced = staging.with_name(staging.name + "-displaced")
    staging.rename(displaced)
    staging.mkdir(mode=0o700)
    try:
        _publish(output, "final")
    except RuntimeError as error:
        assert "identity" in str(error).lower()
    else:
        raise AssertionError("identity mismatch was accepted")
    assert _version(output) == "old"
    assert _journal(output).read_bytes() == retained_journal
    assert staging.exists() and displaced.exists()


def test_output_symlink_is_rejected() -> None:
    root = _root()
    target = root / "target"
    target.mkdir()
    output = root / "bundle"
    output.symlink_to(target, target_is_directory=True)
    try:
        _publish(output, "new")
    except ValueError as error:
        assert "symlink" in str(error).lower()
    else:
        raise AssertionError("output symlink was accepted")
    assert not list(target.iterdir())


def test_cleanup_failure_is_recoverable() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    _publish(output, "middle")
    original = publication._cleanup.remove_exact_tree
    calls = 0

    def fail_once(parent_fd, name, identity):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(errno.EIO, "injected cleanup failure")
        return original(parent_fd, name, identity)

    with mock.patch.object(publication._cleanup, "remove_exact_tree", fail_once):
        try:
            _publish(output, "new")
        except OSError as error:
            assert error.errno == errno.EIO
        else:
            raise AssertionError("cleanup failure was hidden")
    assert _version(output) == "new"
    assert _journal(output).exists() and not _staging_names(output)
    assert len(_retained_names(output)) == 2
    _publish_after_recovery(output, "new", "final")
    assert _version(output) == "final"
    assert not _journal(output).exists() and not _staging_names(output)
    assert len(_retained_names(output)) == 1


def test_active_validation_failure_retains_old_tree_and_journal() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    validations = 0

    def validate(bundle: Path) -> None:
        nonlocal validations
        validations += 1
        assert _version(bundle) == "new"
        if validations == 2:
            raise RuntimeError("active validation failed")

    try:
        publication.publish_bundle(output, _materialize("new"), validate)
    except RuntimeError:
        pass
    else:
        raise AssertionError("active validation failure was hidden")
    assert _version(output) == "new"
    assert _journal(output).exists()
    assert len(_staging_names(output)) == 1
    assert _version(_staging_names(output)[0]) == "old"


def test_concurrent_publishers_serialize() -> None:
    root = _root()
    output, events, ready = root / "bundle", root / "events", root / "ready"
    script = textwrap.dedent(
        """
        import os, sys, time
        from pathlib import Path
        from bundle_publication import publish_bundle
        output, events, ready = map(Path, sys.argv[1:4])
        label, delay = sys.argv[4], float(sys.argv[5])
        def emit(value):
            fd = os.open(events, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try: os.write(fd, (value + "\\n").encode())
            finally: os.close(fd)
        def materialize(staging):
            emit(label + "-start"); ready.touch(); time.sleep(delay)
            (staging / "version").write_text(label); emit(label + "-end")
        publish_bundle(output, materialize, lambda path: (path / "version").read_text())
        """
    )
    env = dict(os.environ, PYTHONPATH=str(TOOLS))
    first = subprocess.Popen(
        [sys.executable, "-c", script, str(output), str(events), str(ready), "a", "0.7"], env=env,
    )
    deadline = time.monotonic() + 5
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists()
    second = subprocess.Popen(
        [sys.executable, "-c", script, str(output), str(events), str(ready), "b", "0"], env=env,
    )
    assert first.wait(timeout=10) == 0
    assert second.wait(timeout=10) == 0
    assert events.read_text().splitlines() == ["a-start", "a-end", "b-start", "b-end"]


def test_native_binding_reports_current_os_errno() -> None:
    root = _root()
    (root / "source").mkdir()
    (root / "target").mkdir()
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        native = publication._NativeRename()
        assert native.function.argtypes is not None
        assert native.function.restype is not None
        try:
            native.no_replace(parent_fd, "source", "target")
        except OSError as error:
            assert error.errno == errno.EEXIST
        else:
            raise AssertionError("native exclusive rename replaced a target")
    finally:
        os.close(parent_fd)


def stat_mode(path: Path) -> int:
    return path.stat(follow_symlinks=False).st_mode & 0o777


def test_unsupported_exchange_remains_recoverable_precommit() -> None:
    output = _root() / "bundle"
    _publish(output, "old")
    unsupported = OSError(errno.ENOTSUP, "exchange unsupported")
    with mock.patch.object(publication._NativeRename, "exchange", side_effect=unsupported):
        try:
            _publish(output, "new")
        except OSError as error:
            assert error.errno == errno.ENOTSUP
        else:
            raise AssertionError("unsupported exchange was hidden")
    assert _version(output) == "old"
    assert _journal(output).exists() and len(_staging_names(output)) == 1
    _publish(output, "final")
    assert _version(output) == "final"


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
