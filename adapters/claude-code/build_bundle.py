#!/usr/bin/env python3
"""Build the pure, self-contained Claude Code bundle-v2 projection."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from adapter_profiles import load_profiles, project_text
from bundle_sync import (
    copy_regular_file,
    prepare_output_root,
    source_files,
    sync_tree,
    write_text_file,
)
from bundle_publication import publish_bundle
from release_contract import validate_bundle, write_bundle_manifest


DIRECT_CHILD_ID = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
LEGACY_TARGETS = (
    "agents/nestjs-backend-engineer.md",
    "agents/python-backend-engineer.md",
    "agents/react-frontend-engineer.md",
    "agents/web-search.md",
    "hooks/bash-pattern-reminder.py",
    "hooks/comment-discipline-reminder.py",
    "hooks/frontend-dead-code.py",
    "hooks/frontend-fsd-gate.py",
    "hooks/nodejs-deps-audit.py",
    "hooks/nodejs-security-scan.py",
    "hooks/nodejs-security-stop-gate.py",
    "hooks/path-validation.py",
    "hooks/python-deps-audit.py",
    "hooks/python-security-scan.py",
    "hooks/python-security-stop-gate.py",
    "hooks/rules",
    "hooks/scan-suppression-markers.py",
    "hooks/stop-gate-suppression-markers.py",
    "skills/code-audit",
    "skills/curl-requests",
    "skills/git-conventional-commits-ru",
    "skills/nestjs-backend-patterns",
    "skills/no-suppression-markers",
    "skills/ops-app-server-safety",
    "skills/python-backend-patterns",
    "skills/react-frontend-patterns",
    "skills/secrets-handling",
    "skills/severity-calibration",
    "skills/shadcn",
    "skills/surface-ticket",
    "skills/task-workflow",
    "skills/testing-strategy",
)


def _require_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"bundle source must be a regular file: {path}")


def _require_tree(path: Path) -> None:
    source_files(path)


def _direct_children(path: Path, *, optional: bool = False) -> list[Path]:
    if optional and not path.exists() and not path.is_symlink():
        return []
    _require_tree(path)
    children = sorted(path.iterdir(), key=lambda child: child.name)
    for child in children:
        if not DIRECT_CHILD_ID.fullmatch(child.name):
            raise ValueError(f"bundle child has invalid release id segment: {child}")
        if child.is_symlink():
            raise ValueError(f"bundle source must not be a symlink: {child}")
        if child.is_dir():
            _require_tree(child)
        elif not child.is_file():
            raise ValueError(f"bundle source must be a file or directory: {child}")
    return children


def _validate_json_object(path: Path) -> None:
    _require_file(path)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(), object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")


def _child_units(children: list[Path], collection: str) -> list[dict[str, Any]]:
    units = []
    for child in children:
        relative = f"{collection}/{child.name}"
        singular = "output-style" if collection == "output-styles" else "rule"
        units.append(
            {
                "id": f"claude-code.{singular}.{child.name}",
                "kind": "tree" if child.is_dir() else "file",
                "source": relative,
                "target": {"root": "claude-config", "path": relative},
                "legacy_source_suffixes": [
                    f"dist/claude-code/{relative}"
                ],
            }
        )
    return units


def _resources() -> list[dict[str, Any]]:
    supported = {"observation": "supported", "apply": "unimplemented"}
    unimplemented = {"observation": "unimplemented", "apply": "unimplemented"}
    return [
        {
            "id": "claude-code.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {"root": "claude-config", "path": "credentials-index.md"},
            **supported,
        },
        {
            "id": "claude-code.settings",
            "strategy": "json-key-merge",
            "source": "settings.json",
            "target": {"root": "claude-config", "path": "settings.json"},
            "legacy_source_suffixes": ["dist/claude-code/settings.json"],
            "owned_json_pointers": [
                "/permissions/allow",
                "/permissions/ask",
                "/permissions/deny",
            ],
            **supported,
        },
    ]


def _mcp_projections() -> list[dict[str, Any]]:
    return [
        {
            "id": "claude-code.mcp.context7",
            "codec": "claude-user-http-v1",
            "server": "context7",
            "profile": "remote-keyless",
            "target": {"root": "home", "path": ".claude.json"},
            "map_pointer": "/mcpServers",
            "entry_key": "context7",
            "registry": {
                "target": {
                    "root": "claude-config",
                    "path": "mainframe/mcp-ownership.json",
                },
                "schema_version": 1,
                "entries_pointer": "/servers",
            },
        }
    ]


def _install_units(
    style_children: list[Path], rule_children: list[Path]
) -> list[dict[str, Any]]:
    units = [
        {
            "id": "claude-code.instructions",
            "kind": "file",
            "source": "CLAUDE.md",
            "target": {"root": "claude-config", "path": "CLAUDE.md"},
            "legacy_source_suffixes": [
                "dist/claude-code/CLAUDE.md",
                "export/CLAUDE.md",
            ],
        },
        {
            "id": "claude-code.plugin",
            "kind": "tree",
            "source": "plugin",
            "target": {"root": "claude-config", "path": "skills/mainframe"},
            "legacy_source_suffixes": [
                "dist/claude-code/plugin",
                "plugin-dist",
            ],
        },
    ]
    units.extend(_child_units(style_children, "output-styles"))
    units.extend(_child_units(rule_children, "rules"))
    return units


def _legacy_artifacts() -> list[dict[str, Any]]:
    return [
        {
            "target": {"root": "claude-config", "path": target},
            "target_suffixes": [f"export/{target}"],
        }
        for target in sorted(LEGACY_TARGETS)
    ]


def materialize(root: Path, output: Path) -> None:
    """Materialize release inputs without reading or mutating user state."""
    instructions = root / "dist/claude-code/CLAUDE.md"
    plugin = root / "dist/claude-code/plugin"
    styles = root / "dist/claude-code/output-styles"
    rules = root / "dist/claude-code/rules"
    settings = root / "dist/claude-code/settings.json"
    credentials = root / "core/resources/credentials-index.md"
    _require_file(instructions)
    _require_tree(plugin)
    style_children = _direct_children(styles)
    rule_children = _direct_children(rules, optional=True)
    _require_file(settings)
    _validate_json_object(settings)
    _require_file(credentials)
    profile = load_profiles(root)["claude-code"]

    expected = {
        "CLAUDE.md",
        "bundle.json",
        "credentials-index.md",
        "plugin",
        "settings.json",
    }
    expected.update({"output-styles"} if style_children else set())
    expected.update({"rules"} if rule_children else set())
    prepare_output_root(output, expected)
    copy_regular_file(instructions, output / "CLAUDE.md")
    copy_regular_file(settings, output / "settings.json")
    write_text_file(
        output / "credentials-index.md",
        project_text(credentials.read_text(), profile),
    )
    sync_tree(plugin, output / "plugin")
    if style_children:
        sync_tree(styles, output / "output-styles")
    if rule_children:
        sync_tree(rules, output / "rules")
    write_bundle_manifest(
        output,
        component="claude-code",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=_install_units(style_children, rule_children),
        legacy_artifacts=_legacy_artifacts(),
        resources=_resources(),
        runtime_profile=asdict(profile),
        mcp_projections=_mcp_projections(),
    )


def build(root: Path, output: Path) -> None:
    """Atomically publish a validated Claude Code bundle."""
    output.parent.mkdir(parents=True, exist_ok=True)
    publish_bundle(
        output,
        lambda staged: materialize(root, staged),
        validate_bundle,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or root / "dist/claude-code/bundle-v2"
    build(root, output)
    print(f"wrote Claude Code bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
