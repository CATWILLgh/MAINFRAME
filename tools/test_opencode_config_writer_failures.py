#!/usr/bin/env python3
"""Tier-1 failure-path tests for secure OpenCode config publication."""

import contextlib
import importlib
import io
import os
import stat
import sys
import tempfile
from unittest import mock

_TOOLS = os.path.dirname(os.path.abspath(__file__))
_OC_ADAPTER = os.path.join(os.path.dirname(_TOOLS), "adapters", "opencode")
sys.path.insert(0, _TOOLS)
sys.path.insert(0, _OC_ADAPTER)
import build_opencode as bo
from test_build_opencode import _fixture_root
from test_opencode_config_writer import (
    _assert_config_error, _assert_no_staging_files, _existing_config, _mode,
    _raw, _serialized,
)


def _owner_module():
    return importlib.import_module(bo.write_config.__module__)


class _WriteFailure:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __enter__(self):
        self.wrapped.__enter__()
        return self

    def __exit__(self, *args):
        return self.wrapped.__exit__(*args)

    def write(self, _data):
        raise OSError("injected staging write failure")

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


@contextlib.contextmanager
def _fail_fdopen_write(number):
    owner = _owner_module()
    original = owner.os.fdopen
    count = 0

    def failing(fd, *args, **kwargs):
        nonlocal count
        count += 1
        opened = original(fd, *args, **kwargs)
        return _WriteFailure(opened) if count == number else opened

    with mock.patch.object(owner.os, "fdopen", side_effect=failing):
        yield


@contextlib.contextmanager
def _fail_fsync(number=None, directory=False):
    owner = _owner_module()
    original = owner.os.fsync
    count = 0

    def failing(fd):
        nonlocal count
        is_directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        if is_directory == directory:
            count += 1
            if number is None or count == number:
                raise OSError("injected fsync failure")
        return original(fd)

    with mock.patch.object(owner.os, "fsync", side_effect=failing):
        yield


@contextlib.contextmanager
def _fail_replace(destination):
    owner = _owner_module()
    original = owner.os.replace

    def failing(source, target):
        if os.path.abspath(target) == os.path.abspath(destination):
            raise OSError("injected replace failure")
        return original(source, target)

    with mock.patch.object(owner.os, "replace", side_effect=failing):
        yield


@contextlib.contextmanager
def _fail_staged_config_unlink():
    owner = _owner_module()
    original = owner.os.unlink
    leaked = []

    def failing(path, *args, **kwargs):
        if os.path.basename(path).startswith(".opencode.json."):
            leaked.append(path)
            raise OSError("injected persistent staging cleanup failure")
        return original(path, *args, **kwargs)

    with mock.patch.object(owner.os, "unlink", side_effect=failing):
        yield leaked


def _assert_failure_state(patch, expected_live, expected_backup):
    with tempfile.TemporaryDirectory() as directory:
        path = _existing_config(directory, backup=b"older backup\n")
        with patch(path):
            _assert_config_error(lambda: bo.write_config(path, {"v": 2}))
        assert _raw(path) == expected_live
        assert _raw(path + ".backup") == expected_backup
        _assert_no_staging_files(directory,
                                 ["opencode.json", "opencode.json.backup"])


def test_staging_write_and_fsync_failures_preserve_both_files():
    old, older = b'{ "v": 1 }\n', b"older backup\n"
    _assert_failure_state(lambda _path: _fail_fdopen_write(1), old, older)
    _assert_failure_state(lambda _path: _fail_fsync(1), old, older)


def test_backup_staging_and_replace_failures_preserve_both_files():
    old, older = b'{ "v": 1 }\n', b"older backup\n"
    _assert_failure_state(lambda _path: _fail_fdopen_write(2), old, older)
    _assert_failure_state(lambda _path: _fail_fsync(2), old, older)
    _assert_failure_state(lambda path: _fail_replace(path + ".backup"),
                          old, older)


def test_live_replace_failure_keeps_live_and_publishes_recovery_backup():
    old = b'{ "v": 1 }\n'
    _assert_failure_state(lambda path: _fail_replace(path), old, old)


def test_directory_fsync_failure_reports_published_state():
    old = b'{ "v": 1 }\n'
    with tempfile.TemporaryDirectory() as directory:
        path = _existing_config(directory, backup=b"older backup\n")
        with _fail_fsync(directory=True):
            _assert_config_error(
                lambda: bo.write_config(path, {"v": 2}),
                "published but durability unconfirmed")
        assert _raw(path) == _serialized({"v": 2})
        assert _raw(path + ".backup") == old
        _assert_no_staging_files(directory,
                                 ["opencode.json", "opencode.json.backup"])


def test_fresh_cleanup_failure_returns_success_with_warning():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "opencode.json")
        with _fail_staged_config_unlink() as leaked:
            result = bo.write_config(path, {"v": 2})
        assert _raw(path) == _serialized({"v": 2})
        assert _mode(path) == 0o600
        assert result.cleanup_warning
        assert len(set(leaked)) == 1
        assert _raw(leaked[0]) == _serialized({"v": 2})
        assert _mode(leaked[0]) == 0o600


def test_fresh_link_failure_leaves_no_outputs():
    owner = _owner_module()
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "opencode.json")
        with mock.patch.object(owner.os, "link",
                               side_effect=OSError("injected link failure")):
            _assert_config_error(lambda: bo.write_config(path, {"v": 2}))
        assert os.listdir(directory) == []


def test_fresh_publication_conflict_preserves_competing_file():
    owner = _owner_module()
    original = owner.os.link
    competing = b"competing writer\n"

    def publish_competitor_then_link(source, target, **kwargs):
        with open(target, "wb") as handle:
            handle.write(competing)
        return original(source, target, **kwargs)

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "opencode.json")
        with mock.patch.object(
                owner.os, "link", side_effect=publish_competitor_then_link):
            _assert_config_error(
                lambda: bo.write_config(path, {"v": 2}),
                "appeared during publication")
        assert _raw(path) == competing
        _assert_no_staging_files(directory, ["opencode.json"])


def test_main_continues_state_publication_after_cleanup_warning():
    root = _fixture_root()
    path = os.path.join(root, "opencode.json")
    output = io.StringIO()
    with _fail_staged_config_unlink(), contextlib.redirect_stdout(output):
        assert bo.main([
            "--root", root,
            "--agents-out", os.path.join(root, "out-agents"),
            "--config", path,
            "--claude-config", os.path.join(root, "absent.json"),
        ]) == 0
    assert os.path.isfile(path + ".mainframe-permissions.json")
    assert "WARNING" in output.getvalue()
    assert "cleanup" in output.getvalue()


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
