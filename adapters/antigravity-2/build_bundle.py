#!/usr/bin/env python3
"""Build the self-contained Antigravity 2.x immutable release bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from bundle_sync import prepare_output_root, remove_path, write_text_file
from release_contract import write_bundle_manifest
from release_contract_fields import HOST_REQUIREMENTS_SCHEMA_VERSION

import build_antigravity
import compatibility


CONFIG_ROOT_TOKEN = "{{mainframe.config_root}}"
ANTIGRAVITY_DATA_PATH = "~/.gemini/antigravity"
EXECUTABLE_PLUGIN_PATHS = {
    Path("memory/store.py"),
    Path("scripts/mainframe_hook.py"),
    Path("scripts/mainframe_state.py"),
}
DEFAULT_BUNDLE_PATH = Path("dist/antigravity-2/bundle")


def _write_plugin(root: Path, output: Path) -> None:
    files = build_antigravity.render_plugin(root)
    remove_path(output)
    output.mkdir(parents=True)
    for relative, content in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        if relative in EXECUTABLE_PLUGIN_PATHS:
            destination.chmod(0o755)


def _credentials_index(root: Path) -> str:
    source = root / "core/resources/credentials-index.md"
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"bundle source must be a regular file: {source}")
    projected = source.read_text().replace(CONFIG_ROOT_TOKEN, ANTIGRAVITY_DATA_PATH)
    if CONFIG_ROOT_TOKEN in projected:
        raise ValueError("Antigravity credentials index retains a runtime token")
    return projected


def _resources() -> list[dict]:
    return [
        {
            "id": "antigravity-2.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "antigravity-data",
                "path": "credentials-index.md",
            },
            "observation": "supported",
            "apply": "unimplemented",
        },
        {
            "id": "antigravity-2.live-activation",
            "strategy": "manual-action",
            "target": {
                "root": "antigravity-config",
                "path": "plugins/mainframe",
            },
            "observation": "unimplemented",
            "apply": "unimplemented",
        },
    ]


def _mcp_projections() -> list[dict]:
    return [{
        "id": "antigravity-2.mcp.context7",
        "codec": "antigravity-global-http-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {
            "root": "antigravity-config",
            "path": "mcp_config.json",
        },
        "map_pointer": "/mcpServers",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "antigravity-data",
                "path": "mainframe/mcp-ownership.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }]


def build(root: Path, output: Path) -> None:
    """Materialize release inputs without reading or mutating user state."""
    root = root.resolve()
    prepare_output_root(
        output,
        {"bundle.json", "credentials-index.md", "plugin"},
    )
    _write_plugin(root, output / "plugin")
    write_text_file(output / "credentials-index.md", _credentials_index(root))
    write_bundle_manifest(
        output,
        component="antigravity-2",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=[
            {
                "id": "antigravity-2.plugin",
                "kind": "tree",
                "source": "plugin",
                "target": {
                    "root": "antigravity-config",
                    "path": "plugins/mainframe",
                },
                "legacy_source_suffixes": ["dist/antigravity-2/plugin"],
            }
        ],
        resources=_resources(),
        mcp_projections=_mcp_projections(),
        schema_version=HOST_REQUIREMENTS_SCHEMA_VERSION,
        host_requirements=compatibility.managed_host_requirements(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or root / DEFAULT_BUNDLE_PATH
    build(root, output)
    print(f"wrote Antigravity 2.x bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
