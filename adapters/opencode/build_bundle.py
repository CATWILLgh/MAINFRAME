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
    prepare_output_root,
    sync_tree,
    write_text_file,
)
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
FEEDBACK_FALLBACK = (
    'os.path.expanduser("~/.claude/skills/harness-feedback")'
)
TELEMETRY_FALLBACK = (
    'os.path.expanduser("~/.claude/mainframe/telemetry/telemetry.db")'
)
OPENCODE_CONFIG_EXPRESSION = (
    'os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")'
)


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
        '  feedbackSkillDir: fileURLToPath(new URL("../skills/harness-feedback", import.meta.url)),\n'
        "  telemetryDb: path.join(process.env.XDG_CONFIG_HOME || "
        'path.join(process.env.HOME || "", ".config"), "opencode", '
        '"mainframe", "telemetry", "telemetry.db"),',
        source,
    )
    row_env = (
        "        env: { ...process.env, CLAUDE_PROJECT_DIR: payload.project_dir,\n"
        "               MAINFRAME_FEEDBACK_SKILL_DIR: runtime.feedbackSkillDir,\n"
        "               MAINFRAME_TELEMETRY_DB: runtime.telemetryDb } },"
    )
    text = _replace_once(text, PLUGIN_ROW_ENV, row_env, source)
    stop_env = (
        "      { cwd, env: { ...process.env, CLAUDE_PROJECT_DIR: cwd,\n"
        "                    MAINFRAME_FEEDBACK_SKILL_DIR: runtime.feedbackSkillDir,\n"
        "                    MAINFRAME_TELEMETRY_DB: runtime.telemetryDb } }, payload)"
    )
    text = _replace_once(text, PLUGIN_STOP_ENV, stop_env, source)
    if "~/.claude" in text or "/.claude/" in text:
        raise ValueError(f"{source}: projected plugin retains a Claude runtime path")
    return text


def _project_skills(root: Path, output: Path, profile) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "skills"
        sync_tree(root / "core/skills", staged)
        for path in sorted(staged.rglob("*.md")):
            write_text_file(
                path, build_opencode.project_runtime_text(path.read_text(), profile)
            )
        sync_tree(staged, output)


def _project_agents(root: Path, output: Path, profile) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "agents"
        staged.mkdir()
        for name, rendered in build_opencode._collect_agents(
            str(root), enrich=None, profile=profile
        ):
            write_text_file(staged / name, rendered)
        sync_tree(staged, output)


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
        text = _replace_once(text, FEEDBACK_FALLBACK, feedback, source)
        text = _replace_once(text, TELEMETRY_FALLBACK, telemetry, source)
    return build_opencode.project_runtime_text(text, profile)


def _project_gates(root: Path, output: Path, profile) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "gates"
        sync_tree(root / "core/gates/detectors", staged / "detectors")
        sync_tree(root / "core/gates/rules", staged / "rules")
        for path in sorted((staged / "detectors").rglob("*.py")):
            write_text_file(path, _project_detector(path.read_text(), path, profile))
        projected = "\n".join(
            path.read_text()
            for path in sorted((staged / "detectors").rglob("*.py"))
        )
        if "~/.claude" in projected or "/.claude/" in projected:
            raise ValueError("projected detectors retain a Claude runtime path")
        sync_tree(staged, output)


def _project_plugin_tree(source: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "plugins"
        write_text_file(staged / "mainframe-gates.js", _project_plugin(source))
        write_text_file(staged / "package.json", '{"type":"module"}\n')
        sync_tree(staged, output)


def build(root: Path, output: Path) -> None:
    """Materialize OpenCode release inputs without reading user state."""
    profile = load_profiles(root)["opencode"]
    agents_source = root / "dist/opencode/AGENTS.md"
    plugin_source = root / "adapters/opencode/plugins/mainframe-gates.js"
    rules_source = root / "core/permissions/rules.json"
    for source in (
        root / "core/skills",
        root / "core/gates/detectors",
        root / "core/gates/rules",
    ):
        if not source.is_dir():
            raise FileNotFoundError(source)
    for source in (agents_source, plugin_source, rules_source):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"bundle source must be a regular file: {source}")
    _validate_agent_sources(root)
    rules = load_permission_rules(str(rules_source))
    permission, report = build_opencode.project_permissions(rules)
    require_restrictive_projection(permission)

    expected = {
        "AGENTS.md",
        "agents",
        "bundle.json",
        "config-fragment.json",
        "gates",
        "plugins",
        "skills",
    }
    prepare_output_root(output, expected)
    _project_gates(root, output / "gates", profile)
    _project_skills(root, output / "skills", profile)
    _project_agents(root, output / "agents", profile)

    agents_text = build_opencode.project_runtime_text(
        agents_source.read_text(), profile
    )
    write_text_file(output / "AGENTS.md", agents_text)
    _project_plugin_tree(plugin_source, output / "plugins")

    fragment = {"permission": permission}
    write_text_file(
        output / "config-fragment.json",
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
    )
    manifest = {
        "adapter": "opencode",
        **asdict(profile),
        "configuration": {
            "permission_fragment": "config-fragment.json",
            "permission_projection_skipped": report["skipped"],
            "mcp_projection": "retired_cross_adapter_import",
        },
    }
    write_text_file(
        output / "bundle.json",
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output or root / "dist/opencode/bundle-v2"
    build(root, output)
    print(f"wrote OpenCode bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
