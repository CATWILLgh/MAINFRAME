#!/usr/bin/env python3
"""Hermetic tests for the immutable packaged MAINFRAME release layout."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import build_release
import release_contract


def test_build_creates_complete_indexed_release_and_executable_layout():
    sandbox = Path(tempfile.mkdtemp())
    output = sandbox / "mainframe-test"

    build_release.build(REPO, output, release_id="test-release")

    index = release_contract.validate_release(output)
    assert [entry["component"] for entry in index["manifests"]] == [
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
    assert (output / "bundles/claude-code/bundle.json").is_file()
    assert (output / "bundles/codex/bundle.json").is_file()
    assert (output / "bundles/opencode/bundle.json").is_file()

    manifests = [
        release_contract.validate_bundle((output / entry["path"]).parent)
        for entry in index["manifests"]
    ]
    by_component = {manifest["component"]: manifest for manifest in manifests}
    for adapter in ("claude-code", "codex", "opencode"):
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
        "credential-tools.bashrc-source",
        "credential-tools.profile-source",
        "credential-tools.secrets-store",
        "credential-tools.zshenv-source",
    }
    shell_resources = {
        resource["target"]["path"]: resource
        for resource in credentials["resources"]
        if resource["target"]["root"] == "home"
    }
    assert shell_resources[".zshenv"]["strategy"] == "shell-line"
    assert shell_resources[".bashrc"]["strategy"] == "shell-line-if-present"
    assert shell_resources[".profile"]["strategy"] == "shell-line-if-present"
    assert all(
        resource["source"] == "shell-source-line"
        for resource in shell_resources.values()
    )
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

    home = sandbox / "home"
    home.mkdir()
    env = dict(
        os.environ,
        HOME=str(home),
        CODEX_HOME=str(home / ".codex"),
        XDG_CONFIG_HOME=str(home / ".config"),
    )
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


def test_build_rejects_existing_destination_without_mutation():
    sandbox = Path(tempfile.mkdtemp())
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
