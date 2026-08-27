#!/usr/bin/env python3
"""Check shared discovery meaning without requiring cross-adapter wording parity."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "adapters" / "claude-code"
CODEX = ROOT / "adapters" / "codex"


def markdown_discovery(path: Path) -> str:
    body = path.read_text(encoding="utf-8")
    values = []
    for field in ("description", "when_to_use"):
        match = re.search(rf"^{field}:\s*(.+)$", body, re.MULTILINE)
        if match:
            values.append(match.group(1).strip().strip('"'))
    assert values, path
    return " ".join(values).casefold()


def codex_agent_discovery(path: Path) -> str:
    return tomllib.loads(path.read_text(encoding="utf-8"))["description"].casefold()


def assert_shared_meaning(claude_path: Path, codex_path: Path, *concepts: str) -> None:
    claude_text = markdown_discovery(claude_path)
    codex_text = (
        codex_agent_discovery(codex_path)
        if codex_path.name.endswith(".toml.template")
        else markdown_discovery(codex_path)
    )
    for concept in concepts:
        expected = concept.casefold()
        assert expected in claude_text, (claude_path, concept)
        assert expected in codex_text, (codex_path, concept)


def test_cross_adapter_skill_meaning_stays_aligned():
    pairs = {
        "curl-requests": ("mainframe-curl-requests", ("bounded http(s) requests", "purpose-built client")),
        "frontend": ("mainframe-frontend", ("client-facing react", "react native", "infrastructure ownership")),
        "infrastructure": ("mainframe-infrastructure", ("project deployment and infrastructure", "ordinary application or ui")),
        "init": ("mainframe-init", ("explicit primary-session collaboration context",)),
        "ops-app-server-safety": ("mainframe-ops-app-server-safety", ("long-running application process", "one-shot build")),
        "project-instructions-audit": ("mainframe-project-instructions-audit", ("instruction hierarchy", "conflicts", "duplication")),
        "project-instructions-init": ("mainframe-project-instructions-init", ("instruction hierarchy", "explicitly")),
        "python-backend-patterns": ("mainframe-python-backend", ("server-side python", "data or ml pipelines", "node.js services")),
        "research-method": ("mainframe-research-method", ("evidence selection", "cross-checking")),
        "testing-strategy": ("mainframe-testing-strategy", ("cross-cutting testing strategy", "routine focused tests")),
        "record-project-problem": (
            "mainframe-record-project-problem",
            ("concrete repository problem", "outside the active task", "one minimal record"),
        ),
        "tickets-find": ("mainframe-tickets-find", ("plausible", "without fixing")),
        "tickets-implement": ("mainframe-tickets-implement", ("autonomous ready tickets", "independent verification")),
        "tickets-refine": ("mainframe-tickets-refine", ("open ticket", "user decision")),
        "tickets-verify": ("mainframe-tickets-verify", ("independently", "archive", "without repairing")),
        "typescript-backend-patterns": ("mainframe-typescript-backend", ("server-side typescript", "client-only ui", "python services")),
    }
    for claude_name, (codex_name, concepts) in pairs.items():
        assert_shared_meaning(
            CLAUDE / "plugin" / "skills" / claude_name / "SKILL.md",
            CODEX / "skills" / codex_name / "SKILL.md",
            *concepts,
        )


def test_cross_adapter_agent_meaning_stays_aligned():
    pairs = {
        "mainframe-advisor.md": ("mainframe_advisor.toml.template", ("final independent readiness check", "earlier adversarial decision challenge")),
        "mainframe-decision-reviewer.md": ("mainframe_decision_reviewer.toml.template", ("independent", "consequential proposed decision", "non-obvious tradeoffs")),
        "mainframe-python-backend-engineer.md": ("mainframe_python_backend_engineer.toml.template", ("bounded server-side python implementation", "trivial edits")),
        "mainframe-react-frontend-engineer.md": ("mainframe_react_frontend_engineer.toml.template", ("bounded implementation", "client-facing react", "trivial edits")),
        "mainframe-researcher.md": ("mainframe_researcher.toml.template", ("bounded external-research block", "repository exploration")),
        "mainframe-test-auditor.md": ("mainframe_test_auditor.toml.template", ("explicitly asked to audit", "test execution cost")),
        "mainframe-typescript-backend-engineer.md": ("mainframe_typescript_backend_engineer.toml.template", ("bounded server-side typescript implementation", "trivial edits")),
    }
    for claude_name, (codex_name, concepts) in pairs.items():
        assert_shared_meaning(
            CLAUDE / "agents" / claude_name,
            CODEX / "agents" / codex_name,
            *concepts,
        )


def test_optional_peer_work_meaning_stays_aligned():
    assert_shared_meaning(
        CLAUDE / "optional" / "skills" / "mainframe-peer-work" / "SKILL.md",
        CODEX / "optional" / "skills" / "mainframe-peer-work" / "SKILL.md",
        "independent review or implementation",
        "same result",
        "start a new session",
    )


def test_public_skills_own_their_primary_result():
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Every public skill must produce its primary result on its own" in contributing

    for exported in (
        CODEX / "export" / "AGENTS.md",
        CLAUDE / "export" / "CLAUDE.md",
    ):
        body = exported.read_text(encoding="utf-8")
        assert "available task-specific skill clearly matches" in body
        assert "load only the supporting resources relevant to the task" in body

    skill_roots = (
        CODEX / "skills",
        CLAUDE / "plugin" / "skills",
    )
    cross_skill_link = re.compile(r"\]\([^)]*/SKILL\.md(?:#[^)]*)?\)")
    for skill_root in skill_roots:
        for skill_file in sorted(skill_root.glob("*/SKILL.md")):
            body = skill_file.read_text(encoding="utf-8")
            assert not cross_skill_link.search(body), skill_file

    assert not (CLAUDE / "plugin" / "skills" / "dokploy-api" / "SKILL.md").exists()
    assert (CLAUDE / "plugin" / "skills" / "infrastructure" / "dokploy.md").is_file()

    for relative in (
        "mainframe-curl-requests/SKILL.md",
        "mainframe-secrets/SKILL.md",
        "mainframe-infrastructure/SKILL.md",
        "mainframe-tickets-implement/SKILL.md",
        "mainframe-tickets-verify/SKILL.md",
    ):
        body = (CODEX / "skills" / relative).read_text(encoding="utf-8")
        assert "absence does not" in " ".join(body.split()), relative

    for relative in (
        "curl-requests/SKILL.md",
        "secrets-handling/SKILL.md",
        "infrastructure/SKILL.md",
        "tickets-implement/SKILL.md",
        "tickets-verify/SKILL.md",
    ):
        body = (CLAUDE / "plugin" / "skills" / relative).read_text(encoding="utf-8")
        assert "absence does not" in " ".join(body.split()), relative


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
