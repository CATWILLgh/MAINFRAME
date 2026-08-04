#!/usr/bin/env python3
"""Tier-1 contract tests for the ZCode Desktop projection."""

from __future__ import annotations

import sys
import tempfile
from importlib import import_module
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
ADAPTER = REPO / "adapters" / "zcode-desktop"
sys.path.insert(0, str(ADAPTER))
sys.path.insert(0, str(REPO / "tools"))
build = import_module("build_zcode")


def test_default_projection_path_cannot_overlap_the_closed_bundle() -> None:
    assert build.DEFAULT_PROJECTION_PATH == Path("dist/zcode-desktop/projection")
    assert build.DEFAULT_PROJECTION_PATH != Path("dist/zcode-desktop")


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)


def frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end]), text[end + 5 :]


def fixture_root() -> Path:
    root = Path(tempfile.mkdtemp())
    for name in build.CORE_INSTRUCTION_FILES:
        write(root / "core/instructions" / name, f"\n{name}\n")
    write(root / "adapters/zcode-desktop/instructions/00-preamble.md", "# ZCode preamble\n")
    write(root / "adapters/zcode-desktop/instructions/90-runtime-zcode-desktop.md", "\n## ZCode runtime\n")
    write(
        root / "core/skills/public-method/SKILL.md",
        "---\nname: public-method\ndescription: Public method.\n"
        "when_to_use: Use for public work.\nuser-invocable: true\n---\n\n"
        "# Public\n\nRun from `~/.claude/skills/mainframe/skills/public-method`.\n",
    )
    write(root / "core/skills/public-method/reference.md", "Use ~/.claude/mainframe safely.\n")
    write(
        root / "core/skills/private-method/SKILL.md",
        "---\nname: private-method\ndescription: Private method.\n"
        "disable-model-invocation: true\n---\n\n"
        "# Private\n\nRead [guide](guide.md) and "
        "[`public-method`](../public-method/SKILL.md), then apply the private rule.\n",
    )
    write(root / "core/skills/private-method/guide.md", "Run `tool.py` from ~/.claude/mainframe.\n")
    write(root / "core/skills/private-method/tool.py", "VALUE = 1\n")
    write(
        root / "core/agents/reviewer.md",
        "---\nname: reviewer\ndescription: Review safely.\n"
        "needs-repo-read: true\nneeds-write: false\nneeds-web: true\n"
        "needs-docs-lookup: false\nreasoning-tier: deep\nbackground: true\n"
        "turn-budget: 12\nmethod-skills:\n  - private-method\n  - public-method\n"
        "---\n\nReview with the preloaded method and [hub](../../dist/claude-code/CLAUDE.md).\n",
    )
    write(
        root / "core/agents/implementer.md",
        "---\nname: implementer\ndescription: Implement safely.\n"
        "needs-repo-read: true\nneeds-write: true\nneeds-web: false\n"
        "needs-docs-lookup: false\nreasoning-tier: standard\nbackground: false\n"
        "---\n\nImplement and verify.\n",
    )
    return root


def test_projection_is_deterministic_and_partitions_private_methods() -> None:
    files = build.render_projection(fixture_root())
    assert list(files) == sorted(files, key=lambda path: path.as_posix())
    assert Path("AGENTS.md") in files
    assert Path("skills/public-method/SKILL.md") in files
    assert Path("skills/private-method/SKILL.md") not in files
    assert Path("mainframe-agent-methods/private-method/SKILL.md") not in files
    assert Path("mainframe-agent-methods/private-method/guide.md") in files
    assert Path("mainframe-agent-methods/private-method/tool.py") in files
    assert Path("agents/reviewer.md") in files
    assert Path("agents/implementer.md") in files


def test_public_skill_frontmatter_is_reduced_to_supported_zcode_fields() -> None:
    files = build.render_projection(fixture_root())
    metadata, body = frontmatter(files[Path("skills/public-method/SKILL.md")].decode())
    assert metadata == {
        "name": "public-method",
        "description": "Public method.",
        "when_to_use": "Use for public work.",
    }
    assert "user-invocable" not in metadata
    assert "disable-model-invocation" not in metadata
    assert "~/.zcode/skills/public-method" in body


def test_agents_use_only_evidenced_tools_and_embed_private_method() -> None:
    files = build.render_projection(fixture_root())
    reviewer_meta, reviewer_body = frontmatter(files[Path("agents/reviewer.md")].decode())
    assert reviewer_meta == {
        "name": "reviewer",
        "description": "Review safely.",
        "tools": ["Glob", "Grep", "Read", "WebFetch", "WebSearch"],
    }
    assert "background" not in reviewer_meta
    assert "model" not in reviewer_meta
    assert "maxTurns" not in reviewer_meta
    assert "$public-method" in reviewer_body
    assert "## Private method: private-method" in reviewer_body
    assert "private rule" in reviewer_body
    assert "~/.zcode/mainframe-agent-methods/private-method/guide.md" in reviewer_body
    assert "~/.zcode/skills/public-method/SKILL.md" in reviewer_body
    assert "roughly 12 steps" in reviewer_body

    implementer_meta, _ = frontmatter(files[Path("agents/implementer.md")].decode())
    assert implementer_meta["tools"] == ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]


def test_projection_removes_stale_claude_paths_from_every_text_file() -> None:
    files = build.render_projection(fixture_root())
    for path, content in files.items():
        if path.suffix == ".md":
            assert "~/.claude" not in content.decode(), path
            assert "dist/claude-code" not in content.decode(), path


def test_missing_or_invalid_method_contract_fails_closed() -> None:
    root = fixture_root()
    agent = root / "core/agents/reviewer.md"
    agent.write_text(agent.read_text().replace("  - public-method\n", "  - absent-method\n"))
    with pytest.raises(ValueError, match="unknown method skills.*absent-method"):
        build.render_projection(root)

    root = fixture_root()
    agent = root / "core/agents/reviewer.md"
    agent.write_text(agent.read_text().replace("needs-write: false", "needs-write: sometimes"))
    with pytest.raises(ValueError, match="needs-write must be a boolean"):
        build.render_projection(root)


def test_missing_instruction_part_and_invalid_skill_fail_closed() -> None:
    root = fixture_root()
    (root / "core/instructions/15-communication.md").unlink()
    with pytest.raises(ValueError, match="missing ZCode instruction part"):
        build.render_projection(root)

    root = fixture_root()
    skill = root / "core/skills/public-method/SKILL.md"
    skill.write_text(skill.read_text().replace("description: Public method.\n", ""))
    with pytest.raises(ValueError, match="missing description"):
        build.render_projection(root)


def test_publish_and_check_are_closed_over_generated_files() -> None:
    root = fixture_root()
    out = root / "dist/zcode-desktop"
    files = build.render_projection(root)
    build.publish_projection(files, out)
    assert build.is_current(files, out)
    write(out / "unexpected.txt", "drift\n")
    assert not build.is_current(files, out)


def test_real_repository_projects_all_neutral_agents_without_private_discovery() -> None:
    files = build.render_projection(REPO)
    agent_paths = {path for path in files if path.parent == Path("agents")}
    expected_agents = {Path("agents") / f"{path.stem}.md" for path in (REPO / "core/agents").glob("*.md")}
    assert agent_paths == expected_agents
    restricted = {
        path.parent.name
        for path in (REPO / "core/skills").glob("*/SKILL.md")
        if "disable-model-invocation: true" in path.read_text()
    }
    assert not any(path.parts[:2] == ("skills", name) for name in restricted for path in files)
    assert not any(path.name == "SKILL.md" and path.parts[0] == "mainframe-agent-methods" for path in files)
    for path, content in files.items():
        if path.suffix in {".md", ".py", ".js", ".json"}:
            assert b"~/.claude" not in content, path
    workflow = files[Path("skills/task-workflow/SKILL.md")].decode()
    workflow_meta, _ = frontmatter(workflow)
    assert "{{mainframe.plans_root}}" not in str(workflow_meta)
    for stale_binding in ("`EnterPlanMode`", "`ExitPlanMode`", "`advisor()`"):
        assert stale_binding not in workflow


def test_runtime_overlay_bounds_native_goal_mode_to_explicit_long_goals() -> None:
    instructions = build.render_projection(REPO)[Path("AGENTS.md")].decode()
    assert "`/goal`" in instructions
    assert "explicitly asks for a long-running goal" in instructions
    assert "Do not create a goal for routine work" in instructions
    assert "MAINFRAME verification" in instructions
