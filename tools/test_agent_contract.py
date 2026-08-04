"""Tier-1 tests for the neutral agent source contract."""

from dataclasses import asdict

import pytest

from agent_contract import AgentContract, AgentSource, parse_agent_source


VALID_SOURCE = """---
name: sample-agent
description: "A focused sample agent."
needs-repo-read: true
needs-write: false
needs-web: true
needs-docs-lookup: false
reasoning-tier: standard
turn-budget: 20
background: true
method-skills:
  - sample-method
---

Body with leading and trailing whitespace.""" + "  \n"


def test_valid_source_returns_typed_contract_and_preserves_body() -> None:
    source = parse_agent_source(VALID_SOURCE, source="core/agents/sample-agent.md")

    assert isinstance(source, AgentSource)
    assert isinstance(source.contract, AgentContract)
    assert asdict(source.contract) == {
        "name": "sample-agent",
        "description": "A focused sample agent.",
        "needs_repo_read": True,
        "needs_write": False,
        "needs_web": True,
        "needs_docs_lookup": False,
        "reasoning_tier": "standard",
        "background": True,
        "turn_budget": 20,
        "method_skills": ("sample-method",),
    }
    assert source.body == "\nBody with leading and trailing whitespace.  \n"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("name: sample-agent\n", "missing opening frontmatter delimiter"),
        ("---\nname: sample-agent\n", "missing closing frontmatter delimiter"),
        ("---\n- sample-agent\n---\nbody", "frontmatter must be a mapping"),
        ("---\n[invalid\n---\nbody", "invalid YAML frontmatter"),
        (
            VALID_SOURCE.replace("description: \"A focused sample agent.\"", "name: duplicate"),
            "duplicate field: name",
        ),
        (
            VALID_SOURCE.replace("description: \"A focused sample agent.\"\n", ""),
            "missing required field: description",
        ),
        (
            VALID_SOURCE.replace("background: true\n", "background: true\nextra: true\n"),
            "unknown field: extra",
        ),
        (
            VALID_SOURCE.replace("needs-write: false", 'needs-write: "false"'),
            "needs-write must be a boolean",
        ),
        (
            VALID_SOURCE.replace("reasoning-tier: standard", "reasoning-tier: extreme"),
            "reasoning-tier must be one of: light, standard, deep",
        ),
        (
            VALID_SOURCE.replace("turn-budget: 20", "turn-budget: true"),
            "turn-budget must be an integer",
        ),
        (
            VALID_SOURCE.replace("turn-budget: 20", "turn-budget: null"),
            "turn-budget must be an integer",
        ),
        (
            VALID_SOURCE.replace("turn-budget: 20", "turn-budget: 0"),
            "turn-budget must be a positive integer",
        ),
        (
            VALID_SOURCE.replace(
                "method-skills:\n  - sample-method", "method-skills: sample-method"
            ),
            "method-skills must be a list",
        ),
        (
            VALID_SOURCE.replace(
                "method-skills:\n  - sample-method", "method-skills: null"
            ),
            "method-skills must be a list",
        ),
        (
            VALID_SOURCE.replace("  - sample-method", "  - 7"),
            "method-skills entries must be strings",
        ),
        (
            VALID_SOURCE.replace("name: sample-agent", "name: ''"),
            "name must be a non-empty kebab-case string",
        ),
        (
            VALID_SOURCE.replace("  - sample-method", "  - ''"),
            "method-skills entries must be non-empty kebab-case names",
        ),
    ],
)
def test_invalid_agent_sources_fail_intentionally(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_agent_source(text, source="core/agents/sample-agent.md")


def test_errors_identify_the_source_without_echoing_input() -> None:
    with pytest.raises(ValueError) as raised:
        parse_agent_source("private malformed content", source="core/agents/private.md")

    assert str(raised.value).startswith("core/agents/private.md: ")
    assert "private malformed content" not in str(raised.value)


def test_optional_fields_may_be_omitted() -> None:
    text = VALID_SOURCE.replace("turn-budget: 20\n", "").replace(
        "method-skills:\n  - sample-method\n", ""
    )

    contract = parse_agent_source(text).contract

    assert contract.turn_budget is None
    assert contract.method_skills == ()
