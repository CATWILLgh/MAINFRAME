#!/usr/bin/env python3
"""Build the unlinked, self-contained OpenCode bundle-v2 projection."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapter_profiles import load_profiles
from bundle_sync import (
    copy_regular_file,
    prepare_output_root,
    sync_tree,
    write_text_file,
)
from bundle_publication import publish_bundle
from detector_projection import project_hooklib_fallbacks
from release_contract import validate_bundle, write_bundle_manifest
import build_opencode
from permission_config import load_permission_rules, require_restrictive_projection


PLUGIN_IMPORT = 'import path from "node:path"'
PLUGIN_SCRIPTS = (
    '  scriptsDir: `${process.env.HOME}/.claude/skills/mainframe/hooks/scripts`,'
)
PLUGIN_ROW_ENV = (
    "        env: { ...process.env, CLAUDE_PROJECT_DIR: payload.project_dir } },"
)
PLUGIN_STOP_ENV = (
    "      { cwd, env: { ...process.env, CLAUDE_PROJECT_DIR: cwd } }, payload)"
)
OPENCODE_CONFIG_EXPRESSION = (
    'os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")'
)
BUNDLE_ENTRIES = {
    "AGENTS.md", "agents", "bundle.json", "config-fragment.json",
    "credentials-index.md", "gates", "memory", "plugins", "skills",
}


def _legacy_sources(source: str) -> list[str]:
    if source == "AGENTS.md":
        return ["dist/opencode/AGENTS.md", "export/AGENTS.md"]
    if source.startswith("agents/"):
        return [f"dist/opencode/{source}"]
    if source.startswith("skills/"):
        return [f"dist/claude-code/plugin/{source}"]
    if source == "plugins/mainframe-gates.js":
        return ["adapters/opencode/plugins/mainframe-gates.js"]
    if source == "plugins/mainframe-memory.js":
        return ["adapters/opencode/plugins/mainframe-memory.js"]
    if source == "memory/store.py":
        return ["core/memory/store.py"]
    if source == "memory/memory-reminder.py":
        return ["core/gates/detectors/memory-reminder.py"]
    return []


def _install_unit(source: str, kind: str) -> dict:
    unit = {
        "id": f"opencode.{source.lower()}",
        "kind": kind,
        "source": source,
        "target": {"root": "opencode-config", "path": source},
    }
    legacy = _legacy_sources(source)
    if legacy:
        unit["legacy_source_suffixes"] = legacy
    return unit


def _install_units(output: Path) -> list[dict]:
    units = [_install_unit("AGENTS.md", "file")]
    for path in sorted((output / "agents").iterdir()):
        units.append(_install_unit(path.relative_to(output).as_posix(), "file"))
    for path in sorted((output / "skills").iterdir()):
        units.append(_install_unit(path.relative_to(output).as_posix(), "tree"))
    for directory in (output / "gates", output / "memory", output / "plugins"):
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            units.append(_install_unit(path.relative_to(output).as_posix(), "file"))
    return units


def _resources() -> list[dict]:
    observed = {"observation": "supported", "apply": "unimplemented"}
    apply_supported = {"observation": "supported", "apply": "supported"}
    return [
        {
            "id": "opencode.credentials-index",
            "strategy": "seed-if-absent",
            "source": "credentials-index.md",
            "target": {
                "root": "opencode-config",
                "path": "credentials-index.md",
            },
            **observed,
        },
        {
            "id": "opencode.permissions",
            "strategy": "json-key-merge",
            "source": "config-fragment.json",
            "target": {"root": "opencode-config", "path": "opencode.json"},
            "ownership": {
                "kind": "json-map-entry-registry-v1",
                "map_pointer": "/permission",
                "entry_schema": "decision-rule-v1",
                "registry": {
                    "target": {
                        "root": "opencode-config",
                        "path": "opencode.json.mainframe-permissions.json",
                    },
                    "schema_version": 1,
                    "entries_pointer": "/actions",
                },
            },
            **apply_supported,
        },
    ]


def _replace_once(text: str, needle: str, replacement: str, source: Path) -> str:
    count = text.count(needle)
    if count != 1:
        raise ValueError(f"{source}: expected one projection anchor, found {count}")
    return text.replace(needle, replacement)


def _project_plugin(source: Path) -> str:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"bundle source must be a regular file: {source}")
    text = source.read_text()
    text = _replace_once(
        text,
        PLUGIN_IMPORT,
        PLUGIN_IMPORT + '\nimport { fileURLToPath } from "node:url"',
        source,
    )
    text = _replace_once(
        text,
        PLUGIN_SCRIPTS,
        '  scriptsDir: fileURLToPath(new URL("../gates/detectors", import.meta.url)),\n'
        '  feedbackSkillDir: fileURLToPath(new URL("../skills/harness-feedback", import.meta.url)),',
        source,
    )
    row_env = (
        "        env: { ...process.env, CLAUDE_PROJECT_DIR: payload.project_dir,\n"
        "               MAINFRAME_FEEDBACK_SKILL_DIR: runtime.feedbackSkillDir } },"
    )
    text = _replace_once(text, PLUGIN_ROW_ENV, row_env, source)
    stop_env = (
        "      { cwd, env: { ...process.env, CLAUDE_PROJECT_DIR: cwd,\n"
        "                    MAINFRAME_FEEDBACK_SKILL_DIR: runtime.feedbackSkillDir } }, payload)"
    )
    text = _replace_once(text, PLUGIN_STOP_ENV, stop_env, source)
    if "~/.claude" in text or "/.claude/" in text:
        raise ValueError(f"{source}: projected plugin retains a Claude runtime path")
    return text


def _project_skills(root: Path, output: Path, profile) -> None:
    sync_tree(root / "core/skills", output)
    for path in sorted(output.rglob("*.md")):
        write_text_file(
            path, build_opencode.project_runtime_text(path.read_text(), profile)
        )


def _project_agents(root: Path, output: Path, profile) -> None:
    agents = build_opencode._collect_agents(str(root), enrich=None, profile=profile)
    prepare_output_root(output, {name for name, _ in agents})
    for name, rendered in agents:
        write_text_file(output / name, rendered)


def _validate_agent_sources(root: Path) -> None:
    source = root / "core/agents"
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"bundle source must be a real directory: {source}")
    for path in source.iterdir():
        if path.suffix == ".md" and (path.is_symlink() or not path.is_file()):
            raise ValueError(f"bundle source must be a regular file: {path}")


def _project_detector(text: str, source: Path, profile) -> str:
    if source.name == "_hooklib.py":
        feedback = (
            f"os.path.join({OPENCODE_CONFIG_EXPRESSION}, "
            '"opencode", "skills", "harness-feedback")'
        )
        telemetry = (
            f"os.path.join({OPENCODE_CONFIG_EXPRESSION}, "
            '"opencode", "mainframe", "telemetry", "telemetry.db")'
        )
        diagnostics = (
            f"os.path.join({OPENCODE_CONFIG_EXPRESSION}, "
            '"opencode", "mainframe", "diagnostics.json")'
        )
        text = project_hooklib_fallbacks(
            text,
            source,
            feedback=feedback,
            telemetry=telemetry,
            diagnostics=diagnostics,
        )
    return build_opencode.project_runtime_text(text, profile)


def _project_gates(root: Path, output: Path, profile) -> None:
    sync_tree(root / "core/gates/detectors", output / "detectors")
    sync_tree(root / "core/gates/rules", output / "rules")
    detectors = sorted((output / "detectors").rglob("*.py"))
    for path in detectors:
        write_text_file(path, _project_detector(path.read_text(), path, profile))
    projected = "\n".join(path.read_text() for path in detectors)
    if "~/.claude" in projected or "/.claude/" in projected:
        raise ValueError("projected detectors retain a Claude runtime path")


def _project_plugin_tree(gates_source: Path, memory_source: Path, output: Path) -> None:
    prepare_output_root(
        output,
        {"mainframe-gates.js", "mainframe-memory.js", "package.json"},
    )
    write_text_file(output / "mainframe-gates.js", _project_plugin(gates_source))
    memory = memory_source.read_text()
    if "~/.claude" in memory or "/.claude/" in memory:
        raise ValueError(
            f"{memory_source}: memory plugin retains a Claude runtime path"
        )
    write_text_file(output / "mainframe-memory.js", memory)
    write_text_file(output / "package.json", '{"type":"module"}\n')


def _project_memory(root: Path, output: Path) -> None:
    sources = {
        "store.py": root / "core/memory/store.py",
        "memory-reminder.py": root / "core/gates/detectors/memory-reminder.py",
    }
    for name, source in sources.items():
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"bundle source must be a regular file: {source}")
        copy_regular_file(source, output / name, executable=True)


def _mcp_projections() -> list[dict]:
    return [{
        "id": "opencode.mcp.context7",
        "codec": "opencode-remote-v1",
        "server": "context7",
        "profile": "remote-keyless",
        "target": {"root": "opencode-config", "path": "opencode.json"},
        "map_pointer": "/mcp",
        "entry_key": "context7",
        "registry": {
            "target": {
                "root": "opencode-config",
                "path": "opencode.json.mainframe-mcp.json",
            },
            "schema_version": 1,
            "entries_pointer": "/servers",
        },
    }]


def materialize(root: Path, output: Path) -> None:
    """Materialize OpenCode release inputs without reading user state."""
    profile = load_profiles(root)["opencode"]
    agents_source = root / "dist/opencode/AGENTS.md"
    gates_plugin_source = root / "adapters/opencode/plugins/mainframe-gates.js"
    memory_plugin_source = root / "adapters/opencode/plugins/mainframe-memory.js"
    rules_source = root / "core/permissions/rules.json"
    credentials_source = root / "core/resources/credentials-index.md"
    for source in (
        root / "core/skills",
        root / "core/gates/detectors",
        root / "core/gates/rules",
    ):
        if not source.is_dir():
            raise FileNotFoundError(source)
    for source in (
        agents_source,
        gates_plugin_source,
        memory_plugin_source,
        rules_source,
        credentials_source,
    ):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"bundle source must be a regular file: {source}")
    _validate_agent_sources(root)
    rules = load_permission_rules(str(rules_source))
    permission, _ = build_opencode.project_permissions(rules)
    require_restrictive_projection(permission)

    prepare_output_root(output, BUNDLE_ENTRIES)
    _project_gates(root, output / "gates", profile)
    _project_memory(root, output / "memory")
    _project_skills(root, output / "skills", profile)
    _project_agents(root, output / "agents", profile)

    agents_text = build_opencode.project_runtime_text(
        agents_source.read_text(), profile
    )
    write_text_file(output / "AGENTS.md", agents_text)
    _project_plugin_tree(gates_plugin_source, memory_plugin_source, output / "plugins")
    fragment = {"permission": permission}
    write_text_file(
        output / "config-fragment.json",
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
    )
    write_text_file(
        output / "credentials-index.md",
        build_opencode.project_runtime_text(credentials_source.read_text(), profile),
    )
    write_bundle_manifest(
        output,
        component="opencode",
        dependencies=["credential-tools", "mainframe-cli"],
        install_units=_install_units(output),
        resources=_resources(),
        runtime_profile=asdict(profile),
        mcp_projections=_mcp_projections(),
    )


def build(root: Path, output: Path) -> None:
    """Atomically publish a validated OpenCode bundle."""
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temporary:
            build(root, Path(temporary) / "bundle-v2")
        print("validated OpenCode bundle without publishing")
        return 0
    output = args.output or root / "dist/opencode/bundle-v2"
    build(root, output)
    print(f"wrote OpenCode bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
