#!/usr/bin/env python3
"""Transaction-lock integration tests for install.sh."""

from __future__ import annotations

import fcntl
import os
import subprocess
import tempfile
import time
from pathlib import Path

from test_install import (
    SYSTEM_PATH,
    _seed_repo,
    _seed_uninstall_links,
)


def _environment(root: Path) -> dict[str, str]:
    return {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_STATE_HOME": str(root / "state"),
        "CODEX_HOME": str(root / "codex"),
        "ANTIGRAVITY_APP": str(root / "Antigravity.app"),
        "PATH": SYSTEM_PATH,
    }


def _run(
    installer: Path,
    args: list[str],
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(installer), *args],
        cwd=installer.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _wait_for_lock_release(lock_path: Path) -> None:
    for _ in range(200):
        with lock_path.open("a+") as contender:
            try:
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            return
    raise AssertionError("descriptor lock was not released after process exit")


def test_uninstall_fails_before_mutation_when_transaction_is_locked() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        state = Path(env["XDG_STATE_HOME"]) / "mainframe"
        state.mkdir(parents=True, mode=0o700)
        lock_path = state / "transaction.lock"
        with lock_path.open("a+") as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = _run(installer, ["--uninstall"], env)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "another MAINFRAME installation is active" in result.stderr
        assert all(link.is_symlink() for link in links)


def test_mutating_run_rejects_relative_state_home() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        env["XDG_STATE_HOME"] = "relative-state"

        result = _run(installer, ["--uninstall"], env)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "unsafe MAINFRAME state base" in result.stderr
        assert all(link.is_symlink() for link in links)


def test_mutating_run_rejects_symlinked_state_root() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        state_base = Path(env["XDG_STATE_HOME"])
        state_base.mkdir()
        foreign = root / "foreign-state"
        foreign.mkdir()
        (state_base / "mainframe").symlink_to(foreign)

        result = _run(installer, ["--uninstall"], env)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "symbolic link in MAINFRAME state path" in result.stderr
        assert all(link.is_symlink() for link in links)


def test_mutating_run_rejects_symlinked_lock_file() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        state = Path(env["XDG_STATE_HOME"]) / "mainframe"
        state.mkdir(parents=True)
        foreign = root / "foreign-lock"
        foreign.write_text("foreign\n")
        (state / "transaction.lock").symlink_to(foreign)

        result = _run(installer, ["--uninstall"], env)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "unsafe MAINFRAME transaction lock" in result.stderr
        assert foreign.read_text() == "foreign\n"
        assert all(link.is_symlink() for link in links)


def test_lock_mode_failure_stops_before_uninstall_mutation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        chmod = fake_bin / "chmod"
        chmod.write_text(
            '#!/bin/sh\ncase "$*" in *transaction.lock*) exit 1;; esac\n'
            'exec /bin/chmod "$@"\n'
        )
        chmod.chmod(0o755)
        env["PATH"] = f"{fake_bin}:{SYSTEM_PATH}"

        result = _run(installer, ["--uninstall"], env)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "could not secure MAINFRAME transaction lock" in result.stderr
        assert all(link.is_symlink() for link in links)


def test_read_only_and_failed_preflight_do_not_create_lock_state() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        env = _environment(root)
        state_base = Path(env["XDG_STATE_HOME"])

        dry_run = _run(installer, ["--dry-run"], env)
        assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
        assert not state_base.exists()

        missing = installer.parent / "dist/claude-code/CLAUDE.md"
        missing.unlink()
        failed = _run(installer, [], env)
        assert failed.returncode != 0, failed.stdout + failed.stderr
        assert not state_base.exists()


def test_successful_uninstall_releases_persistent_private_lock() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        installer = _seed_repo(root)
        links = _seed_uninstall_links(root, installer.parent)
        env = _environment(root)
        env["XDG_STATE_HOME"] = ""

        result = _run(installer, ["--uninstall"], env)

        assert result.returncode == 0, result.stdout + result.stderr
        assert not links[1].exists() and not links[1].is_symlink()
        state = Path(env["HOME"]) / ".local/state/mainframe"
        lock_path = state / "transaction.lock"
        assert state.stat().st_mode & 0o777 == 0o700
        assert lock_path.stat().st_mode & 0o777 == 0o600
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_lock_calls_cover_mutating_main_paths() -> None:
    text = (Path(__file__).resolve().parent.parent / "install.sh").read_text()
    main = text[text.index("main() {"):]
    uninstall = main.index("    if [[ $UNINSTALL -eq 1 ]]; then")
    uninstall_lock = main.index("acquire_transaction_lock", uninstall)
    uninstall_write = main.index("        check_prerequisites", uninstall)
    preflight = main.index("    if ! check_required_install_sources; then")
    install_lock = main.index("acquire_transaction_lock", preflight)
    install_write = main.index("    check_prerequisites", install_lock)

    assert uninstall < uninstall_lock < uninstall_write
    assert preflight < install_lock < install_write


def test_platform_lock_persists_until_shell_closes_descriptor() -> None:
    with tempfile.TemporaryDirectory() as temp:
        lock_path = Path(temp).resolve() / "transaction.lock"
        lock_path.touch(mode=0o600)
        if os.uname().sysname == "Darwin":
            lock_command = "/usr/bin/lockf -s -t 0 9"
        else:
            flock = "/usr/bin/flock" if Path("/usr/bin/flock").exists() else "/bin/flock"
            lock_command = f"{flock} -n 9"
        script = (
            f'exec 9>>"$1"; {lock_command}; '
            'sleep 30 & child=$!; '
            'trap \'kill "$child" 2>/dev/null; wait "$child" 2>/dev/null; '
            'exec 9>&-; exit 0\' TERM INT; '
            'printf "locked\\n"; wait "$child"'
        )
        process = subprocess.Popen(
            ["/bin/bash", "-c", script, "lock-holder", str(lock_path)],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout is not None
            assert process.stdout.readline() == "locked\n"
            with lock_path.open("a+") as contender:
                try:
                    fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise AssertionError("descriptor lock was released too early")
        finally:
            process.terminate()
            process.wait(timeout=5)
        _wait_for_lock_release(lock_path)


def main() -> int:
    tests = [
        value for key, value in sorted(globals().items())
        if key.startswith("test_") and callable(value)
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ok   {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"  FAIL {test.__name__}: {error}")
    print(f"{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
