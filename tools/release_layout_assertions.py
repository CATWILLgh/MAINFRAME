"""Immutable packaged-release layout assertions."""

from __future__ import annotations

import os
from pathlib import Path

import release_contract


def assert_release_layout(output: Path) -> dict:
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
        "zcode-desktop",
    ]
    binary = output / "bin/mainframe"
    assert binary.is_file() and os.access(binary, os.X_OK)
    assert (output / "bin/bundle.json").is_file()
    assert (output / "common/credential-tools/bundle.json").is_file()
    assert (output / "bundles/antigravity-2/bundle.json").is_file()
    assert (output / "bundles/claude-code/bundle.json").is_file()
    assert (output / "bundles/codex/bundle.json").is_file()
    assert (output / "bundles/opencode/bundle.json").is_file()
    assert (output / "bundles/zcode-desktop/bundle.json").is_file()
    assert (output / "metadata/mcp-catalog.json").is_file()
    for item in output.rglob("*"):
        if item.is_file():
            assert item.lstat().st_mode & 0o222 == 0, (
                f"release file is writable: {item}"
            )
    return index
