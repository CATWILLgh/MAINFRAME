---
id: d189a02a
title: Adapter metadata parsers have no shared contract or parity tests
status: closed
priority: low
component: architecture
discovered: 2026-07-15
discovered-from: []
tags: ["architecture", "adapters", "frontmatter", "contract", "drift"]
---

# d189a02a: Adapter metadata parsers have no shared contract or parity tests

## What was observed

Claude Code rendering, OpenCode generation, and Codex generation each parse the same agent or skill frontmatter through separate helpers. Their failure policies already differ: the core renderer raises on malformed delimiters while the Codex parser returns an empty mapping. There is no narrow shared schema or parity fixture proving which keys and malformed inputs each adapter must accept.

No production regression was reproduced during the audit; this is maintainability and contract debt, not an active correctness failure.

## Why it is a problem

Adding a contract field or changing malformed-input handling requires coordinated edits that are easy to miss. An adapter can silently drop metadata while another rejects the same source, and generated goldens may preserve the divergence.

## Why it is not a duplicate

- [#a7c96692](a7c96692-gate-mapping-drift-three-tools.md) covers gate routing, not agent/skill metadata parsing.

## What probably needs to be done

- Define typed schemas for the specific shared contracts instead of one omnibus intermediate representation.
- Share delimiter parsing where semantics are truly common and keep adapter projection explicit.
- Add cross-adapter fixtures for valid, missing, malformed, unknown, and newly introduced fields.

## Acceptance criteria

- Every shared metadata field has one documented source schema and adapter-specific projection tests.
- Malformed frontmatter has an intentional, tested policy on all three adapters.
- Adding a contract field causes a failing test in every adapter that has not handled it.

## Sources

- `tools/render_core.py:335-359`
- `adapters/opencode/build_opencode.py:70-78`
- `adapters/codex/build_codex.py:119-126`

## Resolution

Phase 1 adds the agent-only parser in `tools/agent_contract.py`. It returns
typed `AgentContract` and `AgentSource` values, rejects malformed delimiters,
non-mapping YAML, missing or unknown fields, invalid field types and ranges,
and preserves the source body. Skill parsers remain separate because their
schemas are not the neutral agent contract.

Claude Code, Codex, OpenCode, and Antigravity agent collection now enter
through that parser before applying their native rendering rules. Method-skill
existence remains adapter-specific; the shared parser validates only the name
shape. Cross-adapter tests cover valid input and every intentional failure
class, while committed agent outputs remain byte-equivalent.

Verification: `python3 -m pytest -q tools/test_agent_contract.py
tools/test_render_core.py tools/test_build_codex.py tools/test_build_opencode.py
tools/test_build_antigravity.py`. The two unrelated `curl-requests` drift
failures are tracked separately in ticket `fd61c474`.
