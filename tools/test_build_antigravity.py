#!/usr/bin/env python3
"""Tier-1 contract tests for the Antigravity 2.x adapter builder."""

from __future__ import annotations

import json
import sys
import tempfile
from importlib import import_module
from pathlib import Path
from unittest import TestCase

REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters" / "antigravity-2"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(REPO / "tools"))
build = import_module("build_antigravity")
projection = import_module("skill_projection")
DORMANT_DIAGNOSTICS = b'{\n  "schema_version": 1,\n  "events": false,\n  "feedback": false\n}\n'

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
        "disable-model-invocation: true\n---\n\n# Sample\n\nRun `tool.py`.\n",
    )
    write(root / "core/skills/sample/reference.md", "Use an explicit approval.\n")
    write(
        root / "core/agents/researcher.md",
        "---\nname: researcher\ndescription: Research facts. Picked via empirical tournament "
        "(model:sonnet, effort:low) — 3/3.\nneeds-write: false\n"
        "needs-repo-read: false\nneeds-web: true\nneeds-docs-lookup: true\n"
        "reasoning-tier: light\nbackground: true\nturn-budget: 7\nmethod-skills:\n"
        "  - sample\n---\n\nResearch carefully.\n",
    )
    write(root / "core/gates/detectors/path-validation.py", "print()\n")
    write(
        root / "core/gates/detectors/_hooklib.py",
        'FEEDBACK = os.path.expanduser('
        '"~/.claude/skills/mainframe-dev/skills/harness-feedback")\n'
        'TELEMETRY = os.path.expanduser('
        '"~/.claude/mainframe/telemetry/telemetry.db")\n'
        'DIAGNOSTICS = os.path.expanduser('
        '"~/.claude/mainframe/diagnostics.json")\n',
    )
    write(root / "core/gates/rules/sample.yml", "rules: []\n")
    write(root / "core/memory/store.py", "print('{}')\n")
    write(root / "core/memory/CONTRACT.md", "# Memory\n")
    write(root / "core/resources/credentials-index.md", "Credentials\n")
    write(root / "core/resources/diagnostics.json", DORMANT_DIAGNOSTICS)
    for name, body in {
        "00-preamble.md": "# Antigravity preamble\n",
        "70-memory.md": "# Runtime memory\n",
        "90-runtime-antigravity-2.md": "# Desktop runtime\n",
    }.items():
        write(root / "adapters/antigravity-2/instructions" / name, body)
    write(root / "adapters/antigravity-2/gates/mainframe_hook.py", "print()\n")
    write(root / "adapters/antigravity-2/gates/mainframe_runtime.py", "VALUE = 1\n")
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
        Path("scripts/mainframe_runtime.py"),
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


def assert_source_rejected(root: Path, source: str, forbidden: tuple[str, ...] = ()) -> None:
    try:
        build.render_plugin(root)
    except ValueError as error:
        message = str(error)
        assert source in message
        assert all(value not in message for value in forbidden)
        assert error.__cause__ is None
    else:
        raise AssertionError(f"unsafe Antigravity source was accepted: {source}")


def test_contained_file_link_is_copied_by_value() -> None:
    root = fixture_root()
    target = root / "core/skills/sample/payload.txt"
    write(target, b"contained payload")
    link = target.with_name("linked.txt")
    link.symlink_to(target.name)
    markdown_target = target.with_name("payload.md")
    write(markdown_target, "linked markdown\n")
    markdown_link = target.with_name("linked.md")
    markdown_link.symlink_to(markdown_target.name)
    files = build.render_plugin(root)
    assert files[Path("skills/sample/linked.txt")] == b"contained payload"
    linked_markdown = files[Path("skills/sample/linked.md")].decode()
    assert "core/skills/sample/linked.md" in linked_markdown


def test_external_file_links_are_rejected_at_every_input_boundary() -> None:
    cases = (
        ("core/instructions/linked.md", "core/outside-rule.md"),
        ("core/skills/sample/linked.md", "core/skills/outside.md"),
        ("core/skills/sample/linked.txt", "core/skills/outside.txt"),
        ("core/agents/linked.md", "core/outside-agent.md"),
        ("core/gates/detectors/linked.py", "core/gates/outside.py"),
        ("core/gates/rules/linked.yml", "core/gates/outside.yml"),
        ("core/memory/linked.py", "core/outside-memory.py"),
        ("adapters/antigravity-2/gates/mainframe_runtime.py", "adapters/antigravity-2/outside.py"),
    )
    for source_name, target_name in cases:
        root = fixture_root()
        source = root / source_name
        target = root / target_name
        write(target, "private external bytes")
        source.unlink(missing_ok=True)
        source.symlink_to(target)
        assert_source_rejected(
            root, source_name, (target_name, "private external bytes")
        )


def test_external_link_error_does_not_expose_absolute_target() -> None:
    root = fixture_root()
    outside = Path(tempfile.mkdtemp()) / "private.txt"
    write(outside, "outside repository secret")
    source = root / "core/skills/sample/external.txt"
    source.symlink_to(outside)
    assert_source_rejected(
        root,
        "core/skills/sample/external.txt",
        (str(outside), "outside repository secret"),
    )


def test_broken_and_cyclic_file_links_are_rejected() -> None:
    root = fixture_root()
    broken = root / "core/skills/sample/broken.txt"
    broken.symlink_to("missing.txt")
    assert_source_rejected(root, "core/skills/sample/broken.txt")

    root = fixture_root()
    first = root / "core/gates/detectors/cycle-a.py"
    second = first.with_name("cycle-b.py")
    first.symlink_to(second.name)
    second.symlink_to(first.name)
    assert_source_rejected(root, "core/gates/detectors/cycle-a.py")


def test_contained_and_external_directory_links_are_rejected() -> None:
    cases = (
        ("linked-directory", "payload"),
        ("linked-directory", "../outside-payload"),
        ("linked.pyc", "payload"),
        ("__pycache__", "payload"),
    )
    for link_name, target_name in cases:
        root = fixture_root()
        skill = root / "core/skills/sample"
        target = skill / target_name
        write(target / "data.txt", "payload")
        link = skill / link_name
        link.symlink_to(target, target_is_directory=True)
        assert_source_rejected(root, f"core/skills/sample/{link_name}")


def test_source_root_directory_link_is_rejected() -> None:
    root = fixture_root()
    skill = root / "core/skills/sample"
    target = skill.with_name("real-sample")
    skill.rename(target)
    skill.symlink_to(target.name, target_is_directory=True)
    assert_source_rejected(root, "core/skills/sample")


def test_missing_bridge_error_uses_repository_relative_path() -> None:
    root = fixture_root()
    source_name = "adapters/antigravity-2/gates/mainframe_state.py"
    (root / source_name).unlink()
    assert_source_rejected(root, source_name, (str(root),))


def test_hooks_use_stable_desktop_plugin_path_and_all_official_events() -> None:
    hooks = json.loads(build.render_plugin(fixture_root())[Path("hooks.json")].decode())
    assert set(hooks) == {"mainframe"}
    namespace = hooks["mainframe"]
    assert set(namespace) == {"PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"}
    commands = set()
    for event, entries in namespace.items():
        if event in {"PreToolUse", "PostToolUse"}:
            assert all("matcher" in entry and "hooks" in entry for entry in entries)
            handlers = [hook for entry in entries for hook in entry["hooks"]]
        else:
            assert all("matcher" not in entry and "hooks" not in entry for entry in entries)
            handlers = entries
        assert all(handler["timeout"] == build.HANDLER_TIMEOUT_SECONDS[event] for handler in handlers)
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
        assert "core/instructions/10-partnership.md" in str(error)
        assert str(root) not in str(error)
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


def test_agent_projection_rejects_noncanonical_contract_fields() -> None:
    root = fixture_root()
    agent = root / "core/agents/researcher.md"
    agent.write_text(agent.read_text().replace("needs-web: true", "needs-web: true\nneeds-mcp: true"))
    assert_source_rejected(root, "core/agents/researcher.md")


def test_agent_projection_rejects_unknown_method_at_adapter_boundary() -> None:
    root = fixture_root()
    agent = root / "core/agents/researcher.md"
    agent.write_text(agent.read_text().replace("  - sample", "  - unknown-method"))
    assert_source_rejected(root, "core/agents/researcher.md")


def test_skill_projection_keeps_supported_frontmatter_and_rewrites_bindings() -> None:
    files = build.render_plugin(fixture_root())
    meta, body = build.parse_frontmatter(files[Path("skills/sample/SKILL.md")].decode())
    adapted = build.adapt_runtime_markdown("Use `~/.claude/skills/mainframe/skills/sample/tool.py`, `AskUserQuestion`, `ExitPlanMode`, and {{mainframe.plans_root}}.")
    assert set(meta) == {"name", "description"}
    assert "Run `tool.py`" in body
    assert "~/.gemini/config/plugins/mainframe/skills/sample/tool.py" in adapted
    assert "~/.gemini/antigravity/mainframe-plans" in adapted
    assert "AskUserQuestion" not in adapted and "ExitPlanMode" not in adapted
    assert build.adapt_runtime_markdown("PRELOADED into a subagent.") == "Available to a subagent."


def test_skill_projection_anchor_drift_fails_closed() -> None:
    root = fixture_root()
    sample = root / "core/skills/sample"
    sample.rename(sample.with_name("secrets-handling"))
    assert_source_rejected(root, "core/skills/secrets-handling/SKILL.md")
    case = TestCase()
    source = (REPO / "core/skills/task-workflow/SKILL.md").read_text()
    drifted = source.replace("synthesis → advisor → execution", "synthesis → review → execution")
    case.assertRaisesRegex(ValueError, "core/skills/task-workflow/SKILL.md", build.adapt_skill_markdown, "task-workflow", Path("SKILL.md"), drifted)
    plan = (REPO / "core/skills/task-workflow/plan-file.md").read_text()
    drifted_plan = plan.replace("same Phase 1-4 without the tool", "same phases without the tool")
    case.assertRaisesRegex(ValueError, "core/skills/task-workflow/plan-file.md", build.adapt_skill_markdown, "task-workflow", Path("plan-file.md"), drifted_plan)


def test_unlisted_runtime_sensitive_skill_fails_closed() -> None:
    root = fixture_root()
    path = root / "core/skills/sample/SKILL.md"
    path.write_text(path.read_text() + "\nPreloaded into a subagent.\n")
    assert_source_rejected(root, "sample")
    root = fixture_root()
    path = root / "core/skills/sample/SKILL.md"
    path.write_text(path.read_text() + "\n{{mainframe.plans_root}}\n")
    assert_source_rejected(root, "sample")
    case = TestCase()
    case.assertRaisesRegex(ValueError, "targets missing", projection.validate_skill_projection_inventory, {"task-workflow": {"SKILL.md": "allowedPrompts"}})
    for marker in ("ALLOWEDPROMPTS", "Advisor #1", "advisor tool", "Settings.json", "~/.ZSHENV", "DENIED BY HOOK", "Verified against Claude Code plan mode", "Claude Code tool (path injected)", "built-in Other"):
        root = fixture_root()
        sample = root / "core/skills/sample"
        sample.rename(sample.with_name("code-audit"))
        claims = root / "core/skills/code-audit/CLAIMS.MD"
        claims.write_text(marker + "\n")
        assert_source_rejected(root, "core/skills/code-audit/CLAIMS.MD")
        root = fixture_root()
        agent = root / "core/agents/researcher.md"
        agent.write_text(agent.read_text() + "\n" + marker + "\n")
        assert_source_rejected(root, "core/agents/researcher.md")


def test_real_skill_projection_preserves_method_without_false_guarantees() -> None:
    files = build.render_plugin(REPO)
    def skill(name: str, file: str = "SKILL.md") -> str:
        return files[Path("skills") / name / file].decode()
    secrets = skill("secrets-handling")
    curl = skill("curl-requests")
    workflow = skill("task-workflow")
    plan = skill("task-workflow", "plan-file.md")
    projected = {name: "\n".join(content.decode() for path, content in files.items() if path.parts[:2] == ("skills", name) and path.suffix == ".md") for name in projection.SKILL_PROJECTION_POLICIES}
    assert all(projected.values())
    for phrase in ("a read-only search subagent subagent", "a project `MAINFRAME plugin rules`", "MAINFRAME plugin rules rules", "available into", "allowedPrompts", "denied by `settings.json`", "permissions.deny", "auto-sourced from `~/.zshenv`", "shell subprocess reads `~/.zshenv`", "loaded into the shell environment by `~/.zshenv`", "auto-mode classifier", "enforces denial of direct reads", "{{mainframe.plans_root}}", "~/.claude/plans"):
        assert all(phrase not in text for text in projected.values())
    assert "denied by hook" not in secrets
    assert "`secret get NAME`" in secrets and "already present in the command environment" in secrets
    assert "Pre-reply self-scan" in secrets and "forbidden by this policy" in secrets
    assert "loaded into the shell environment by `~/.zshenv`" not in curl
    for phrase in ("advisor()", "allowedPrompts", "interactive interactive", "Claude Code tool", "Verified against Claude Code", "(Claude Code:", "built-in Other"):
        assert phrase not in workflow + plan
    required = ("### 2. Recon-first (always)", "### 3. Plan — audit file when ≥ 3 phases or ≥ 3 edge-cases", "**6a. High cost-of-being-wrong", "**6b. Then invoke a fresh dynamic reviewer", "### 8. Execution", "TDD — non-negotiable", "### 9. Verification after each execution sub-agent", "### 10. Out-of-scope findings → ticket", "### 11. Edge-case sweep", "### 12. Independent review checkpoint #2", "### 13. Git safety check", "### 14. Commit via", "mainframe-plans/audit/<basename(cwd)>", "../delegate-decision-reviewer/SKILL.md", "../delegate-web-search/SKILL.md")
    assert all(phrase in workflow for phrase in required)
    step_6a = workflow.split("**6a.", 1)[1].split("**6b.", 1)[0]
    step_6b = workflow.split("**6b.", 1)[1].split("### 7.", 1)[0]
    step_12 = workflow.split("### 12.", 1)[1].split("### 13.", 1)[0]
    assert all("define and invoke a fresh" in section for section in (step_6a, step_6b, step_12))
    assert "before a `/goal`" in workflow
    assert "**Boundary** = `/goal` set" in workflow
    assert "if `/goal` is set, treat the plan as approved and continue without another confirmation" in workflow
    assert "interactive sessions (`/goal` auto-approves the plan; otherwise written plans await an explicit go)" in workflow
    assert "| Interactive plan approval | `/goal` auto-approves; otherwise present the plan in chat and await an explicit go" in plan
    assert "If `/goal` is set, continue under its automatic plan approval" in plan
    assert "explicit go" in workflow and "explicit go" in plan


def test_check_detects_drift_and_dry_run_does_not_write() -> None:
    root = fixture_root()
    out = root / "dist/antigravity-2/plugin"
    assert build.main(["--root", str(root), "--out", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert build.main(["--root", str(root), "--out", str(out)]) == 0
    assert build.main(["--root", str(root), "--out", str(out), "--check"]) == 0
    (out / "plugin.json").write_text("{}\n")
    assert build.main(["--root", str(root), "--out", str(out), "--check"]) == 1


def test_split_rule_text_is_lossless_and_respects_the_cap():
    sections = [f"## Section {index}\n\n{'x' * 400}\n\n" for index in range(20)]
    text = "".join(sections)

    parts = build.split_rule_text(text, limit=2000)

    assert len(parts) > 1
    assert all(len(part) <= 2000 for part in parts)
    assert "".join(parts) == text
    assert all(part.startswith("## ") for part in parts)


def test_split_rule_text_keeps_a_short_document_whole():
    text = "## Only\n\nbody\n"

    assert build.split_rule_text(text, limit=2000) == [text]


def test_split_rule_text_rejects_a_section_larger_than_the_cap():
    text = "## Huge\n\n" + "x" * 3000

    try:
        build.split_rule_text(text, limit=2000)
    except ValueError as error:
        assert "exceeds" in str(error)
    else:
        raise AssertionError("oversized section was accepted")


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
