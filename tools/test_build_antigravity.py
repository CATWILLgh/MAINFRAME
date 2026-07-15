#!/usr/bin/env python3
"""Tier-1 contract tests for the Antigravity 2.x adapter builder."""

from __future__ import annotations

import json
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters" / "antigravity-2"
sys.path.insert(0, str(ADAPTER))
import build_antigravity as build


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def fixture_root() -> Path:
    root = Path(tempfile.mkdtemp())
    write(root / "core/instructions/05-title.md", "# MAINFRAME\n")
    write(root / "core/instructions/10-partnership.md", "## Partnership\n\nBe exact.\n")
    write(
        root / "core/skills/sample/SKILL.md",
        "---\nname: sample\ndescription: Sample method.\nuser-invocable: false\n"
        "disable-model-invocation: true\n---\n\n# Sample\n\nRun "
        "`~/.claude/skills/mainframe/skills/sample/tool.py` and use `AskUserQuestion`.\n",
    )
    write(root / "core/skills/sample/reference.md", "Use `ExitPlanMode`.\n")
    write(
        root / "core/agents/researcher.md",
        "---\nname: researcher\ndescription: Research facts. Picked via empirical tournament "
        "(model:sonnet, effort:low) — 3/3.\nneeds-write: false\n"
        "needs-web: true\nneeds-mcp: true\nturn-budget: 7\nmethod-skills:\n"
        "  - sample\n---\n\nResearch carefully.\n",
    )
    write(root / "core/gates/detectors/path-validation.py", "print()\n")
    write(root / "core/gates/detectors/_hooklib.py", "VALUE = 1\n")
    write(root / "core/gates/rules/sample.yml", "rules: []\n")
    write(root / "core/memory/store.py", "print('{}')\n")
    write(root / "core/memory/CONTRACT.md", "# Memory\n")
    for name, body in {
        "00-preamble.md": "# Antigravity preamble\n",
        "70-memory.md": "# Runtime memory\n",
        "90-runtime-antigravity-2.md": "# Desktop runtime\n",
    }.items():
        write(root / "adapters/antigravity-2/instructions" / name, body)
    write(root / "adapters/antigravity-2/gates/mainframe_hook.py", "print()\n")
    write(root / "adapters/antigravity-2/gates/mainframe_state.py", "VALUE = 1\n")
    return root


def test_plan_is_deterministic_and_self_contained() -> None:
    root = fixture_root()
    files = build.render_plugin(root)

    assert list(files) == sorted(files, key=lambda item: item.as_posix())
    expected = {
        Path("plugin.json"),
        Path("hooks.json"),
        Path("rules/core-05-title.md"),
        Path("rules/core-10-partnership.md"),
        Path("rules/adapter-00-preamble.md"),
        Path("skills/sample/SKILL.md"),
        Path("skills/sample/reference.md"),
        Path("skills/delegate-researcher/SKILL.md"),
        Path("scripts/mainframe_hook.py"),
        Path("scripts/mainframe_state.py"),
        Path("scripts/detectors/path-validation.py"),
        Path("scripts/detectors/_hooklib.py"),
        Path("scripts/rules/sample.yml"),
        Path("memory/store.py"),
        Path("memory/CONTRACT.md"),
    }
    assert expected <= set(files)
    assert not any(path.name == "GEMINI.md" for path in files)

    manifest = json.loads(files[Path("plugin.json")].decode())
    assert manifest["name"] == "mainframe"
    assert manifest["version"] == build.ADAPTER_VERSION


def test_projection_excludes_runtime_bytecode_caches() -> None:
    root = fixture_root()
    write(root / "core/memory/__pycache__/store.cpython-313.pyc", b"bytecode")
    write(root / "core/skills/sample/__pycache__/tool.cpython-313.pyc", b"bytecode")

    files = build.render_plugin(root)

    assert not any("__pycache__" in path.parts for path in files)
    assert not any(path.suffix in {".pyc", ".pyo"} for path in files)


def test_hooks_use_stable_desktop_plugin_path_and_all_official_events() -> None:
    hooks = json.loads(build.render_plugin(fixture_root())[Path("hooks.json")].decode())
    assert set(hooks) == {"mainframe"}
    namespace = hooks["mainframe"]
    assert set(namespace) == {
        "PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"
    }
    commands = set()
    for event, entries in namespace.items():
        if event in {"PreToolUse", "PostToolUse"}:
            assert all("matcher" in entry and "hooks" in entry for entry in entries)
            handlers = [hook for entry in entries for hook in entry["hooks"]]
        else:
            assert all("matcher" not in entry and "hooks" not in entry for entry in entries)
            handlers = entries
        commands.update(handler["command"] for handler in handlers)
    assert commands == {
        "python3 ~/.gemini/config/plugins/mainframe/scripts/mainframe_hook.py " + event
        for event in namespace
    }


def test_rule_limit_is_measured_in_characters() -> None:
    root = fixture_root()
    path = root / "core/instructions/10-partnership.md"
    path.write_text("é" * build.RULE_MAX_CHARS)
    assert build.render_plugin(root)[Path("rules/core-10-partnership.md")].decode()

    path.write_text("é" * (build.RULE_MAX_CHARS + 1))
    try:
        build.render_plugin(root)
    except ValueError as error:
        assert "characters" in str(error)
    else:
        raise AssertionError("oversized Antigravity rule was accepted")


def test_delegate_skill_uses_only_documented_capability_booleans() -> None:
    files = build.render_plugin(fixture_root())
    text = files[Path("skills/delegate-researcher/SKILL.md")].decode()
    meta, body = build.parse_frontmatter(text)

    assert meta["name"] == "delegate-researcher"
    assert "define_subagent" in body and "invoke_subagent" in body
    assert "enable_write_tools: false" in body
    assert "enable_mcp_tools: true" in body
    assert "enable_subagent_tools: false" in body
    assert "skills/sample/SKILL.md" in body
    assert "must read" in body.lower()
    assert "soft turn budget: 7" in body.lower()
    assert "model" not in body.lower()
    assert "effort" not in body.lower()


def test_skill_projection_keeps_supported_frontmatter_and_rewrites_bindings() -> None:
    files = build.render_plugin(fixture_root())
    meta, body = build.parse_frontmatter(files[Path("skills/sample/SKILL.md")].decode())
    reference = files[Path("skills/sample/reference.md")].decode()

    assert set(meta) == {"name", "description"}
    assert "~/.gemini/config/plugins/mainframe/skills/sample/tool.py" in body
    assert "AskUserQuestion" not in body
    assert "ExitPlanMode" not in reference


def test_check_detects_drift_and_dry_run_does_not_write() -> None:
    root = fixture_root()
    out = root / "dist/antigravity-2/plugin"

    assert build.main(["--root", str(root), "--out", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert build.main(["--root", str(root), "--out", str(out)]) == 0
    assert build.main(["--root", str(root), "--out", str(out), "--check"]) == 0

    (out / "plugin.json").write_text("{}\n")
    assert build.main(["--root", str(root), "--out", str(out), "--check"]) == 1


def test_native_validation_requires_antigravity_major_two() -> None:
    root = fixture_root()
    app = root / "Antigravity.app"
    plist = app / "Contents/Info.plist"
    plist.parent.mkdir(parents=True)
    with plist.open("wb") as handle:
        plistlib.dump({
            "CFBundleIdentifier": build.BUNDLE_IDENTIFIER,
            "CFBundleShortVersionString": "2.2.1",
        }, handle)

    assert build.validate_native_app(app) == "2.2.1"
    with plist.open("wb") as handle:
        plistlib.dump({
            "CFBundleIdentifier": build.BUNDLE_IDENTIFIER,
            "CFBundleShortVersionString": "3.0.0",
        }, handle)
    try:
        build.validate_native_app(app)
    except ValueError as error:
        assert "major version 2" in str(error)
    else:
        raise AssertionError("Antigravity 3.x was accepted")

    with plist.open("wb") as handle:
        plistlib.dump({
            "CFBundleIdentifier": "com.example.unrelated",
            "CFBundleShortVersionString": "2.2.1",
        }, handle)
    try:
        build.validate_native_app(app)
    except ValueError as error:
        assert build.BUNDLE_IDENTIFIER in str(error)
    else:
        raise AssertionError("an unrelated 2.x application was accepted")


def test_real_builder_cli_check_and_default_output() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "plugin"
        subprocess.run(
            [sys.executable, str(ADAPTER / "build_antigravity.py"),
             "--root", str(REPO), "--out", str(out)],
            check=True,
        )
        subprocess.run(
            [sys.executable, str(ADAPTER / "build_antigravity.py"),
             "--root", str(REPO), "--out", str(out), "--check"],
            check=True,
        )
        meta, body = build.parse_frontmatter(
            (out / "skills/delegate-web-search/SKILL.md").read_text()
        )
        assert meta["name"] == "delegate-web-search"
        assert "define_subagent" in body
        for path in out.glob("skills/delegate-*/SKILL.md"):
            projected = path.read_text()
            assert "dist/claude-code" not in projected
            assert "`skills:` frontmatter" not in projected
            assert "preloaded" not in projected.lower()
            assert "~/.claude/" not in projected
            assert "CLAUDE.md" not in projected


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
