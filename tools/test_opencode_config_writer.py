#!/usr/bin/env python3
"""Tier-1 contract tests for secure OpenCode config publication."""

import contextlib
import io
import json
import math
import multiprocessing
import os
import stat
import sys
import tempfile

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_OC_ADAPTER = os.path.join(os.path.dirname(_TOOLS), "adapters", "opencode")
sys.path.insert(0, _TOOLS)
sys.path.insert(0, _OC_ADAPTER)
import build_opencode as bo
from test_build_opencode import USER_CONFIG, _fixture_root, _write


@contextlib.contextmanager
def _umask(mask):
    previous = os.umask(mask)
    try:
        yield
    finally:
        os.umask(previous)


def _mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


def _raw(path):
    with open(path, "rb") as handle:
        return handle.read()


def _raw_ignoring_mode(path):
    mode = _mode(path)
    os.chmod(path, 0o600)
    try:
        return _raw(path)
    finally:
        os.chmod(path, mode)


def _serialized(data):
    return (json.dumps(data, indent=2) + "\n").encode()


def _assert_result(result, previous, mode, tightened):
    assert result.__class__.__name__ == "ConfigWriteResult"
    assert result.previous_mode == previous
    assert result.mode == mode
    assert result.tightened is tightened


def _assert_config_error(call, phrase=None):
    try:
        call()
    except Exception as exc:
        assert exc.__class__.__name__ == "ConfigWriteError", repr(exc)
        if phrase:
            assert phrase in str(exc), str(exc)
        return
    raise AssertionError("unsafe config write unexpectedly succeeded")


def _assert_no_staging_files(directory, expected):
    assert sorted(os.listdir(directory)) == sorted(expected)


def _existing_config(directory, mode=0o600, backup=None):
    path = os.path.join(directory, "opencode.json")
    _write(path, '{ "v": 1 }\n')
    os.chmod(path, mode)
    if backup is not None:
        _write(path + ".backup", backup.decode())
        os.chmod(path + ".backup", 0o600)
    return path


def test_serialization_failure_creates_nothing():
    root = tempfile.mkdtemp()
    path = os.path.join(root, "missing", "nested", "opencode.json")
    try:
        bo.write_config(path, {"bad": {object()}})
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("serialization unexpectedly succeeded")
    assert os.listdir(root) == []


def test_nan_serialization_failure_creates_nothing():
    root = tempfile.mkdtemp()
    path = os.path.join(root, "missing", "nested", "opencode.json")
    try:
        bo.write_config(path, {"bad": math.nan})
    except ValueError:
        pass
    else:
        raise AssertionError("NaN serialization unexpectedly succeeded")
    assert os.listdir(root) == []


def test_fresh_write_is_0600_under_any_umask():
    for mask in (0o0000, 0o0777):
        with tempfile.TemporaryDirectory() as directory, _umask(mask):
            path = os.path.join(directory, "opencode.json")
            result = bo.write_config(path, {"v": 1})
            assert _mode(path) == 0o600
            assert _raw(path) == _serialized({"v": 1})
            assert not os.path.lexists(path + ".backup")
            _assert_result(result, None, 0o600, False)


def test_new_nested_parents_are_exactly_0700():
    for mask in (0o0000, 0o0777):
        with tempfile.TemporaryDirectory() as root, _umask(mask):
            parents = [os.path.join(root, "a"), os.path.join(root, "a", "b")]
            path = os.path.join(parents[-1], "c", "opencode.json")
            parents.append(os.path.dirname(path))
            bo.write_config(path, {"v": 1})
            assert [_mode(parent) for parent in parents] == [0o700] * 3


def test_existing_0600_is_preserved():
    with tempfile.TemporaryDirectory() as directory:
        path = _existing_config(directory)
        result = bo.write_config(path, {"v": 2})
        assert _mode(path) == 0o600
        _assert_result(result, 0o600, 0o600, False)


def test_weak_and_execute_bits_tighten_to_0600_and_are_reported():
    for weak_mode in (0o644, 0o755, 0o677):
        with tempfile.TemporaryDirectory() as directory:
            path = _existing_config(directory, weak_mode)
            result = bo.write_config(path, {"v": 2})
            assert _mode(path) == 0o600
            _assert_result(result, weak_mode, 0o600, True)


def test_existing_0400_remains_0400():
    with tempfile.TemporaryDirectory() as directory:
        path = _existing_config(directory, 0o400)
        result = bo.write_config(path, {"v": 2})
        assert _mode(path) == 0o400
        _assert_result(result, 0o400, 0o400, False)


def test_write_only_and_no_access_files_are_unchanged():
    for inaccessible_mode in (0o200, 0o000):
        with tempfile.TemporaryDirectory() as directory:
            path = _existing_config(directory, inaccessible_mode)
            before = _raw_ignoring_mode(path)
            _assert_config_error(lambda: bo.write_config(path, {"v": 2}))
            assert _mode(path) == inaccessible_mode
            assert _raw_ignoring_mode(path) == before
            assert not os.path.lexists(path + ".backup")


def test_backup_is_raw_previous_file_and_no_looser_than_live():
    for original_mode in (0o644, 0o400):
        with tempfile.TemporaryDirectory() as directory:
            path = _existing_config(directory, original_mode)
            previous = _raw(path)
            bo.write_config(path, {"v": 2})
            backup = path + ".backup"
            assert _raw(backup) == previous
            assert _mode(backup) & ~_mode(path) == 0


def _assert_rejected_entry(path, check_unchanged, extra_entries=()):
    backup = path + ".backup"
    _write(backup, "older backup\n")
    before_backup = _raw(backup)
    _assert_config_error(lambda: bo.write_config(path, {"v": 2}))
    check_unchanged()
    assert _raw(backup) == before_backup
    expected = [os.path.basename(path), os.path.basename(backup)]
    _assert_no_staging_files(os.path.dirname(path), expected + list(extra_entries))


def test_valid_symlink_is_refused_without_changes():
    with tempfile.TemporaryDirectory() as directory:
        target = os.path.join(directory, "target.json")
        _write(target, "target bytes\n")
        path = os.path.join(directory, "opencode.json")
        os.symlink(target, path)
        before = _raw(target)
        _assert_rejected_entry(
            path,
            lambda: (os.path.islink(path) and _raw(target) == before) or
            (_ for _ in ()).throw(AssertionError("symlink changed")),
            [os.path.basename(target)],
        )


def test_dangling_symlink_is_refused_without_changes():
    with tempfile.TemporaryDirectory() as directory:
        target = os.path.join(directory, "missing.json")
        path = os.path.join(directory, "opencode.json")
        os.symlink(target, path)
        _assert_rejected_entry(path, lambda: (
            os.path.islink(path) and not os.path.exists(target)) or
            (_ for _ in ()).throw(AssertionError("dangling link changed")))


def test_directory_target_is_refused_without_changes():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "opencode.json")
        os.mkdir(path)
        marker = os.path.join(path, "marker")
        _write(marker, "unchanged\n")
        _assert_rejected_entry(path, lambda: (
            _raw(marker) == b"unchanged\n") or
            (_ for _ in ()).throw(AssertionError("directory changed")))


def _fifo_writer_child(path, queue):
    try:
        bo.write_config(path, {"v": 2})
    except Exception as exc:
        queue.put((exc.__class__.__name__, str(exc)))
    else:
        queue.put(("success", ""))


def test_fifo_target_is_refused_without_changes():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "opencode.json")
        os.mkfifo(path)
        _write(path + ".backup", "older backup\n")
        before_backup = _raw(path + ".backup")
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        process = ctx.Process(target=_fifo_writer_child, args=(path, queue))
        process.start()
        process.join(1)
        if process.is_alive():
            process.terminate()
            process.join()
            raise AssertionError("FIFO target caused a blocking write")
        kind, _ = queue.get(timeout=1)
        assert kind == "ConfigWriteError", kind
        assert stat.S_ISFIFO(os.lstat(path).st_mode)
        assert _raw(path + ".backup") == before_backup
        _assert_no_staging_files(directory,
                                 ["opencode.json", "opencode.json.backup"])


def _main_output_for_mode(mode):
    root = _fixture_root()
    config = os.path.join(root, "opencode.json")
    _write(config, json.dumps(USER_CONFIG))
    os.chmod(config, mode)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert bo.main([
            "--root", root,
            "--agents-out", os.path.join(root, "out-agents"),
            "--config", config,
            "--claude-config", os.path.join(root, "absent.json"),
        ]) == 0
    return output.getvalue()


def test_main_reports_only_actual_permission_tightening():
    tightened = _main_output_for_mode(0o644)
    preserved = _main_output_for_mode(0o600)
    assert "tightened permissions" in tightened
    assert "0644" in tightened and "0600" in tightened
    assert "tightened permissions" not in preserved


def _run_all():
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
