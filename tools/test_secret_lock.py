#!/usr/bin/env python3
"""Tier-1 contract tests for legacy credential-store locking."""

import os
import subprocess
import tempfile
import time
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SECRET = REPO / "core/resources/credential-tools/secret"
LOCKED_STORE = "secret: another instance holds the lock (waited 5s, giving up)\n"
RECOVERED_LOCK = "secret: recovered stale lock\n"
LIVE_LOCK = "secret: lock owner is still running; refusing recovery\n"
FOREIGN_LOCK = "secret: lock belongs to another host; refusing recovery\n"
UNKNOWN_LOCK = (
    "secret: lock owner is unknown; verify no secret process is running, "
    "then use --confirm-unknown\n"
)


def _workspace() -> tuple[Path, Path, Path, dict[str, str]]:
    root = Path(tempfile.mkdtemp(prefix="secret-lock-test-"))
    config = root / "config"
    lock = config / "credentials/.lock"
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(config),
        "PATH": os.environ["PATH"],
    }
    return root, config, lock, env


def _dead_pid() -> int:
    process = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
    process.wait()
    return process.pid


def _recover(env: dict[str, str], confirmation: str = "--confirm") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(SECRET), "recover-lock", confirmation],
        capture_output=True,
        env=env,
        check=False,
    )


def test_stale_lock_blocks_all_writers_until_explicit_recovery() -> None:
    _, _, lock, env = _workspace()
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{_dead_pid()}\n")
    processes = [
        subprocess.Popen(
            [str(SECRET), "set", name, "DO_NOT_LEAK_VALUE"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        for name in ("FIRST_TOKEN", "SECOND_TOKEN")
    ]
    results = [process.communicate() for process in processes]

    assert [process.returncode for process in processes] == [1, 1]
    assert all(stdout == b"" for stdout, _ in results)
    assert all(stderr == LOCKED_STORE.encode() for _, stderr in results)
    assert all(b"DO_NOT_LEAK_VALUE" not in stderr for _, stderr in results)
    assert lock.is_dir()


def test_dead_local_owner_recovers_but_foreign_owner_does_not() -> None:
    _, config, lock, env = _workspace()
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{_dead_pid()}\n")
    (lock / "host").write_text("different-host\n")

    foreign = _recover(env)
    (lock / "host").unlink()
    unknown = _recover(env)
    recovered = _recover(env, "--confirm-unknown")
    written = subprocess.run(
        [str(SECRET), "set", "API_TOKEN", "new-value"],
        capture_output=True,
        env=env,
        check=False,
    )

    assert foreign.returncode == 1
    assert foreign.stderr.decode() == FOREIGN_LOCK
    assert unknown.returncode == 1
    assert unknown.stderr.decode() == UNKNOWN_LOCK
    assert recovered.returncode == 0, recovered.stderr.decode()
    assert recovered.stderr.decode() == RECOVERED_LOCK
    assert written.returncode == 0, written.stderr.decode()
    assert (config / "credentials/secrets.env").read_text() == "API_TOKEN='new-value'\n"


def test_recovery_refuses_live_owner_and_metadata_has_no_value() -> None:
    root, _, lock, env = _workspace()
    initial = subprocess.run(
        [str(SECRET), "set", "API_TOKEN", "DO_NOT_LEAK_VALUE"],
        capture_output=True,
        env=env,
        check=False,
    )
    marker, release, editor = root / "started", root / "release", root / "editor"
    editor.write_text(
        '#!/bin/sh\n: > "$EDITOR_MARKER"\n'
        'while [ ! -e "$EDITOR_RELEASE" ]; do sleep 0.05; done\n'
    )
    editor.chmod(0o700)
    env.update({"EDITOR": str(editor), "EDITOR_MARKER": str(marker), "EDITOR_RELEASE": str(release)})
    owner = subprocess.Popen(
        [str(SECRET), "edit"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    try:
        for _ in range(100):
            if marker.exists():
                break
            time.sleep(0.05)
        assert marker.exists()
        metadata = b"".join(path.read_bytes() for path in lock.iterdir())
        result = _recover(env)
    finally:
        release.touch()
        owner_output = owner.communicate(timeout=5)

    assert initial.returncode == 0, initial.stderr.decode()
    assert owner.returncode == 0, owner_output[1].decode()
    assert b"DO_NOT_LEAK_VALUE" not in metadata + result.stderr
    assert result.returncode == 1
    assert result.stderr.decode() == LIVE_LOCK


def test_only_one_concurrent_recovery_removes_stale_lock() -> None:
    _, _, lock, env = _workspace()
    lock.mkdir(parents=True)
    (lock / "pid").write_text(f"{_dead_pid()}\n")
    (lock / "host").write_bytes(subprocess.check_output(["hostname"]))
    processes = [
        subprocess.Popen(
            [str(SECRET), "recover-lock", "--confirm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        for _ in range(2)
    ]
    results = [process.communicate() for process in processes]

    assert sorted(process.returncode for process in processes) == [0, 1]
    assert sum(stderr == RECOVERED_LOCK.encode() for _, stderr in results) == 1
    assert not lock.exists()


def test_unknown_owner_requires_stronger_confirmation() -> None:
    _, _, lock, env = _workspace()
    lock.mkdir(parents=True)

    refused = _recover(env)
    recovered = _recover(env, "--confirm-unknown")

    assert refused.returncode == 1
    assert refused.stderr.decode() == UNKNOWN_LOCK
    assert recovered.returncode == 0
    assert recovered.stderr.decode() == RECOVERED_LOCK
    assert not lock.exists()


def test_missing_lock_and_busy_recovery_fail_closed() -> None:
    _, config, _, env = _workspace()
    (config / "credentials").mkdir(parents=True)
    missing = _recover(env)
    (config / "credentials/.lock-recovery").mkdir()
    busy = _recover(env)

    assert missing.returncode == 1
    assert missing.stderr == b"secret: no recoverable lock is present\n"
    assert busy.returncode == 1
    assert busy.stderr == b"secret: lock recovery is already in progress\n"


def test_signal_ends_writer_instead_of_continuing_unlocked() -> None:
    root, config, _, env = _workspace()
    editor = root / "interrupt-editor"
    editor.write_text('#!/bin/sh\nkill -TERM "$PPID"\n')
    editor.chmod(0o700)
    env["EDITOR"] = str(editor)

    result = subprocess.run(
        [str(SECRET), "edit"], capture_output=True, env=env, check=False
    )

    assert result.returncode == 143
    assert result.stdout == b""
    assert not (config / "credentials/.lock").exists()


if __name__ == "__main__":
    test_stale_lock_blocks_all_writers_until_explicit_recovery()
    test_dead_local_owner_recovers_but_foreign_owner_does_not()
    test_recovery_refuses_live_owner_and_metadata_has_no_value()
    test_only_one_concurrent_recovery_removes_stale_lock()
    test_unknown_owner_requires_stronger_confirmation()
    test_missing_lock_and_busy_recovery_fail_closed()
    test_signal_ends_writer_instead_of_continuing_unlocked()
    print("7/7 passed")
