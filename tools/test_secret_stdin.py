#!/usr/bin/env python3
"""Tier-1 contract tests for the credential helper's stdin write path."""

import os
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SECRET = REPO / "core/resources/credential-tools/secret"
MAX_STDIN_VALUE_BYTES = 16 * 1024
INVALID_STDIN_VALUE = "secret: stdin value is invalid\n"
EXISTING_SECRET = "secret: stdin secret cannot replace an existing entry\n"
UNSAFE_STORE = "secret: credential store is unsafe\n"


def _run(*args: str, input_value: bytes = b"") -> tuple[subprocess.CompletedProcess[bytes], Path]:
    root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PATH": os.environ["PATH"],
    }
    result = subprocess.run(
        [str(SECRET), *args],
        input=input_value,
        capture_output=True,
        env=env,
        check=False,
    )
    return result, root / "config/credentials/secrets.env"


def test_create_stdin_stores_exact_single_line_and_private_mode() -> None:
    result, store = _run("create-stdin", "API_TOKEN", input_value=b"value with ' quote")

    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b""
    assert store.read_text() == "API_TOKEN='value with '\\'' quote'\n"
    assert store.stat().st_mode & 0o777 == 0o600


def test_set_value_argument_remains_supported() -> None:
    result, store = _run("set", "API_TOKEN", "argument-value")

    assert result.returncode == 0, result.stderr.decode()
    assert store.read_text() == "API_TOKEN='argument-value'\n"


def test_help_describes_create_stdin() -> None:
    result, _ = _run("help")

    assert result.returncode == 0, result.stderr.decode()
    assert b"secret create-stdin NAME" in result.stdout


def test_create_stdin_accepts_value_at_byte_limit() -> None:
    value = b"a" * MAX_STDIN_VALUE_BYTES
    result, store = _run("create-stdin", "API_TOKEN", input_value=value)

    assert result.returncode == 0, result.stderr.decode()
    assert store.read_bytes() == b"API_TOKEN='" + value + b"'\n"


def test_create_stdin_rejects_invalid_values_without_output() -> None:
    cases = (
        b"",
        b"trailing-newline\n",
        b"first\nsecond",
        b"carriage\rreturn",
        b"before\x00after",
        b"a" * (MAX_STDIN_VALUE_BYTES + 1),
    )

    for input_value in cases:
        result, store = _run("create-stdin", "API_TOKEN", input_value=input_value)

        assert result.returncode != 0
        assert result.stdout == b""
        assert result.stderr.decode() == INVALID_STDIN_VALUE
        assert not store.exists()


def test_create_stdin_never_replaces_existing_value() -> None:
    root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PATH": os.environ["PATH"],
    }
    initial = subprocess.run(
        [str(SECRET), "set", "API_TOKEN", "existing-value"],
        capture_output=True,
        env=env,
        check=False,
    )
    result = subprocess.run(
        [str(SECRET), "create-stdin", "API_TOKEN"],
        input=b"new-value",
        capture_output=True,
        env=env,
        check=False,
    )
    store = root / "config/credentials/secrets.env"

    assert initial.returncode == 0, initial.stderr.decode()
    assert result.returncode != 0
    assert result.stdout == b""
    assert result.stderr.decode() == EXISTING_SECRET
    assert store.read_text() == "API_TOKEN='existing-value'\n"


def test_create_stdin_preserves_unrelated_entries() -> None:
    root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PATH": os.environ["PATH"],
    }
    initial = subprocess.run(
        [str(SECRET), "set", "OTHER_TOKEN", "existing-value"],
        capture_output=True,
        env=env,
        check=False,
    )
    result = subprocess.run(
        [str(SECRET), "create-stdin", "API_TOKEN"],
        input=b"new-value",
        capture_output=True,
        env=env,
        check=False,
    )
    store = root / "config/credentials/secrets.env"

    assert initial.returncode == 0, initial.stderr.decode()
    assert result.returncode == 0, result.stderr.decode()
    assert store.read_text() == (
        "OTHER_TOKEN='existing-value'\n"
        "API_TOKEN='new-value'\n"
    )


def test_concurrent_create_allows_exactly_one_writer() -> None:
    root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PATH": os.environ["PATH"],
    }
    processes = [
        subprocess.Popen(
            [str(SECRET), "create-stdin", "API_TOKEN"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        for _ in range(2)
    ]
    results = [
        process.communicate(input=value)
        for process, value in zip(processes, (b"first-value", b"second-value"))
    ]
    return_codes = [process.returncode for process in processes]
    store = root / "config/credentials/secrets.env"

    assert sorted(return_codes) == [0, 1]
    assert all(stdout == b"" for stdout, _ in results)
    failures = [
        stderr
        for process, (_, stderr) in zip(processes, results)
        if process.returncode != 0
    ]
    assert failures == [EXISTING_SECRET.encode()]
    content = store.read_text()
    assert content in (
        "API_TOKEN='first-value'\n",
        "API_TOKEN='second-value'\n",
    )


def test_replacement_and_deletion_sanitize_legacy_backup() -> None:
    root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
    env = {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "PATH": os.environ["PATH"],
    }
    for command in (
        ("set", "API_TOKEN", "retired-value"),
        ("set", "API_TOKEN", "current-value"),
    ):
        result = subprocess.run(
            [str(SECRET), *command],
            capture_output=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode()
    store = root / "config/credentials/secrets.env"
    backup = root / "config/credentials/secrets.env.bak"
    assert b"retired-value" not in store.read_bytes()
    assert b"retired-value" not in backup.read_bytes()

    result = subprocess.run(
        [str(SECRET), "del", "API_TOKEN"],
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"current-value" not in store.read_bytes()
    assert b"current-value" not in backup.read_bytes()


def test_create_stdin_rejects_symlinked_store_targets() -> None:
    for target_name in ("credentials", "secrets.env", "secrets.env.bak"):
        root = Path(tempfile.mkdtemp(prefix="secret-stdin-test-"))
        config = root / "config"
        store_dir = config / "credentials"
        external = root / "external"
        external.mkdir()
        if target_name == "credentials":
            config.mkdir()
            store_dir.symlink_to(external, target_is_directory=True)
            protected = external / "protected"
        else:
            store_dir.mkdir(parents=True)
            protected = external / "protected"
            protected.write_text("unchanged")
            (store_dir / target_name).symlink_to(protected)
        env = {
            "HOME": str(root / "home"),
            "XDG_CONFIG_HOME": str(config),
            "PATH": os.environ["PATH"],
        }

        result = subprocess.run(
            [str(SECRET), "create-stdin", "API_TOKEN"],
            input=b"new-value",
            capture_output=True,
            env=env,
            check=False,
        )

        assert result.returncode != 0
        assert result.stdout == b""
        assert result.stderr.decode() == UNSAFE_STORE
        if protected.exists():
            assert protected.read_text() == "unchanged"
        if target_name == "credentials":
            assert list(external.iterdir()) == []


if __name__ == "__main__":
    test_create_stdin_stores_exact_single_line_and_private_mode()
    test_set_value_argument_remains_supported()
    test_help_describes_create_stdin()
    test_create_stdin_accepts_value_at_byte_limit()
    test_create_stdin_rejects_invalid_values_without_output()
    test_create_stdin_never_replaces_existing_value()
    test_create_stdin_preserves_unrelated_entries()
    test_concurrent_create_allows_exactly_one_writer()
    test_replacement_and_deletion_sanitize_legacy_backup()
    test_create_stdin_rejects_symlinked_store_targets()
    print("10/10 passed")
