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
        "pi-business-analysis": ("mainframe-pi-business-analysis", ("project-scoped pi business analyst", "ordinary discussion")),
        "pi-engineer": ("mainframe-pi-engineer", ("project-scoped pi coding worker", "requirements discovery")),
        "project-instructions-audit": ("mainframe-project-instructions-audit", ("instruction hierarchy", "conflicts", "duplication")),
        "project-instructions-init": ("mainframe-project-instructions-init", ("instruction hierarchy", "explicitly")),
        "python-backend-patterns": ("mainframe-python-backend", ("server-side python", "data or ml pipelines", "node.js services")),
        "research-method": ("mainframe-research-method", ("evidence selection", "cross-checking")),
        "testing-strategy": ("mainframe-testing-strategy", ("cross-cutting testing strategy", "routine focused tests")),
        "ticket": ("mainframe-ticket", ("outside the active task", "without expanding scope")),
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


def test_optional_peer_review_meaning_stays_aligned():
    assert_shared_meaning(
        CLAUDE / "optional" / "skills" / "mainframe-peer-review" / "SKILL.md",
        CODEX / "optional" / "skills" / "mainframe-peer-review" / "SKILL.md",
        "bounded independent review",
        "peer-review checkpoint",
        "ordinary second opinions",
    )


if __name__ == "__main__":
    tests = sorted(name for name in globals() if name.startswith("test_"))
    for name in tests:
        globals()[name]()
        print(f"  ok  {name}")
    print(f"\n{len(tests)}/{len(tests)} passed")
