#!/usr/bin/env python3
"""Hermetic tests for the immutable packaged MAINFRAME release layout."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_release
import release_contract
from release_draft_assertions import assert_machine_draft_reviews
from release_lifecycle_assertions import (
    assert_adapter_lifecycle_plans,
    assert_adapter_plans,
)


def snapshot_tree(path: Path) -> dict[str, tuple[int, bytes | str | None]]:
    snapshot = {}
    for item in [path, *sorted(path.rglob("*"))]:
        relative = item.relative_to(path).as_posix() or "."
        mode = item.lstat().st_mode
        if item.is_symlink():
            content = os.readlink(item)
        elif item.is_file():
            content = item.read_bytes()
        else:
            content = None
        snapshot[relative] = (mode, content)
    return snapshot


def run_dry_run(builder: Path, root: Path) -> subprocess.CompletedProcess[str]:
    sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
    temporary = sandbox / "temporary"
    temporary.mkdir()
    result = subprocess.run(
        [sys.executable, str(builder), "--root", str(root), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
        env=dict(os.environ, TMPDIR=str(temporary)),
    )
    assert list(temporary.iterdir()) == [], "dry-run publication metadata survived"
    return result


def assert_late_failure_preserves_bundle(
    builder,
    root: Path,
    output: Path,
    attribute: str,
) -> None:
    builder.build(root, output)
    before = snapshot_tree(output)
    original = getattr(builder, attribute)

    def reject(*args, **kwargs):
        if attribute == "materialize":
            original(*args, **kwargs)
        raise RuntimeError(f"late {attribute} failure")

    setattr(builder, attribute, reject)
    try:
        try:
            builder.build(root, output)
        except RuntimeError as exc:
            assert str(exc) == f"late {attribute} failure"
        else:
            raise AssertionError(f"late {attribute} failure was ignored")
    finally:
        setattr(builder, attribute, original)
    assert snapshot_tree(output) == before
    release_contract.validate_bundle(output)


def _assert_release_layout(output: Path) -> dict:
    index = release_contract.validate_release(output)
    assert index["schema_version"] == 2
    assert index["mcp_catalog"]["path"] == "metadata/mcp-catalog.json"
    assert [entry["component"] for entry in index["manifests"]] == [
        "antigravity-2",
        "claude-code",
        "codex",
        "credential-tools",
        "mainframe-cli",
        "opencode",
    ]
    binary = output / "bin/mainframe"
    assert binary.is_file() and os.access(binary, os.X_OK)
    assert (output / "bin/bundle.json").is_file()
    assert (output / "common/credential-tools/bundle.json").is_file()
    assert (output / "bundles/antigravity-2/bundle.json").is_file()
    assert (output / "bundles/claude-code/bundle.json").is_file()
    assert (output / "bundles/codex/bundle.json").is_file()
    assert (output / "bundles/opencode/bundle.json").is_file()
    assert (output / "metadata/mcp-catalog.json").is_file()
    for item in output.rglob("*"):
        if item.is_file():
            assert item.lstat().st_mode & 0o222 == 0, (
                f"release file is writable: {item}"
            )
    return index


def _assert_component_contracts(output: Path, index: dict) -> Path:
    manifests = [
        release_contract.validate_bundle((output / entry["path"]).parent)
        for entry in index["manifests"]
    ]
    by_component = {manifest["component"]: manifest for manifest in manifests}
    for adapter in ("antigravity-2", "claude-code", "codex", "opencode"):
        assert by_component[adapter]["dependencies"] == [
            "credential-tools",
            "mainframe-cli",
        ]
    cli_unit = by_component["mainframe-cli"]["install_units"]
    assert cli_unit == [
        {
            "id": "mainframe-cli.binary",
            "kind": "file",
            "source": "mainframe",
            "target": {"root": "user-bin", "path": "mainframe"},
        }
    ]
    credentials = by_component["credential-tools"]
    assert credentials["install_units"][0]["target"] == {
        "root": "user-bin",
        "path": "secret",
    }
    assert {resource["id"] for resource in credentials["resources"]} == {
        "credential-tools.secrets-store",
    }
    store = output / "common/credential-tools/secrets.env"
    assert store.read_bytes() == b""
    assert stat.S_IMODE(store.stat().st_mode) == 0o400
    assert not (output / "common/credential-tools/shell-source-line").exists()
    assert all(
        resource["observation"] == "supported"
        for resource in credentials["resources"]
    )
    assert all(
        resource["apply"] == "unimplemented"
        for resource in credentials["resources"]
    )
    return output / "bin/mainframe"


def _assert_release_cli(binary: Path, output: Path, sandbox: Path) -> None:
    _assert_secret_help(output)
    home = sandbox / "home"
    home.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        CODEX_HOME=str(home / ".codex"),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_STATE_HOME=str(home / ".local/state"),
    )
    _assert_embedded_cli_guidance(binary, sandbox, env)
    assert_machine_draft_reviews(binary, home, sandbox, env, snapshot_tree)
    installed_store = home / ".config/credentials/secrets.env"
    assert stat.S_IMODE(installed_store.stat().st_mode) == 0o600
    _assert_no_shell_startup_files(home)
    _assert_tui_launch(binary, sandbox, env)
    assert_adapter_plans(binary, output, sandbox, env)
    assert_adapter_lifecycle_plans(binary, output, sandbox, env)
    _assert_no_publication_residue(output)


def _assert_embedded_cli_guidance(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
) -> None:
    standalone = sandbox / "standalone-mainframe"
    shutil.copy2(binary, standalone)
    detached_env = dict(env, MAINFRAME_RELEASE_ROOT="/does/not/exist")
    checks = [
        (["--help"], "written only after a final preview and confirmation"),
        (["docs", "list"], "agent-automation"),
        (["docs", "show", "overview"], "# MAINFRAME overview"),
    ]
    for args, expected in checks:
        result = subprocess.run(
            [str(standalone), *args],
            text=True,
            capture_output=True,
            env=detached_env,
            check=True,
            timeout=10,
        )
        assert result.stderr == ""
        assert expected in result.stdout
    capabilities = subprocess.run(
        [str(standalone), "capabilities", "--json"],
        text=True,
        capture_output=True,
        env=detached_env,
        check=True,
        timeout=10,
    )
    contract = json.loads(capabilities.stdout)
    assert contract["schema_version"] == 1
    assert contract["kind"] == "mainframe-capabilities"


def _assert_secret_help(output: Path) -> None:
    secret_help = subprocess.run(
        [str(output / "common/credential-tools/secret"), "help"],
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout
    assert "Each coding environment keeps its own credentials index" in secret_help
    assert "${XDG_CONFIG_HOME:-$HOME/.config}/credentials/secrets.env" in secret_help
    assert "~/.claude" not in secret_help
    assert "~/.config/credentials" not in secret_help
    assert "install.sh" not in secret_help
    assert "$(secret get NAME)" in secret_help


def _assert_no_shell_startup_files(home: Path) -> None:
    assert not any((home / name).exists() for name in (
        ".zshenv", ".bashrc", ".profile",
    ))


def _assert_named_secret_guidance(output: Path) -> None:
    targets = [
        output / "common/credential-tools/secret",
        *output.glob("bundles/*/**/skills/secrets-handling/SKILL.md"),
        *output.glob("bundles/*/**/skills/curl-requests/SKILL.md"),
    ]
    assert len(targets) == 9
    forbidden = (
        "auto-sourced from",
        "loaded into the shell environment by",
        "The store is sourced by",
        "source ~/.zshenv",
        "set -a",
        "The MAINFRAME configuration flow manages this line",
    )
    for target in targets:
        text = target.read_text()
        assert "$(secret get " in text
        assert not any(phrase in text for phrase in forbidden), target


def _assert_tui_launch(
    binary: Path,
    sandbox: Path,
    env: dict[str, str],
) -> None:
    preview = subprocess.run(
        [str(binary)],
        input="q",
        text=True,
        capture_output=True,
        cwd=sandbox,
        env=env,
        timeout=30,
    )
    assert preview.returncode == 0, (preview.stdout, preview.stderr)
    assert preview.stderr == ""


def _assert_no_publication_residue(output: Path) -> None:
    forbidden = (".lock", ".journal", ".publication.json", ".staging-")
    metadata = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if any(marker in path.name for marker in forbidden)
    ]
    assert metadata == []


def test_build_creates_complete_indexed_release_and_executable_layout():
    sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
    output = sandbox / "mainframe-test"

    build_release.build(REPO, output, release_id="test-release")

    index = _assert_release_layout(output)
    binary = _assert_component_contracts(output, index)
    _assert_named_secret_guidance(output)
    _assert_release_cli(binary, output, sandbox)


def test_build_rejects_existing_destination_without_mutation():
    sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
    output = sandbox / "release"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep")

    try:
        build_release.build(REPO, output, release_id="test-release")
    except ValueError as exc:
        assert "must not already exist" in str(exc)
    else:
        raise AssertionError("existing release destination was replaced")

    assert sentinel.read_text() == "keep"
    assert list(output.iterdir()) == [sentinel]


def test_projection_failure_leaves_no_release_or_staging_residue():
    sandbox = Path(tempfile.mkdtemp()).resolve(strict=True)
    output = sandbox / "release"
    original = build_release.project_release_secret_guidance

    def reject(_):
        raise ValueError("projection anchor drift")

    build_release.project_release_secret_guidance = reject
    try:
        try:
            build_release.build(REPO, output, release_id="test-release")
        except ValueError as exc:
            assert str(exc) == "projection anchor drift"
        else:
            raise AssertionError("projection failure was ignored")
    finally:
        build_release.project_release_secret_guidance = original

    assert not output.exists()
    assert list(sandbox.iterdir()) == []


def _run_all():
    failures = 0
    tests = [
        (name, function)
        for name, function in sorted(globals().items())
        if name.startswith("test_") and callable(function)
    ]
    for name, function in tests:
        try:
            function()
            print(f"  ok  {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    _run_all()
