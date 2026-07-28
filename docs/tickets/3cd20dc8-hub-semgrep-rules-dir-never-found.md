---
id: 3cd20dc8
title: Hub semgrep rule frontend-token-storage.yml is silently inactive — gate looks in scripts/rules, file ships in hooks/rules
status: closed
priority: medium
component: hooks
discovered: 2026-07-08
discovered-from: []
tags: ["security", "hooks", "semgrep", "silent-fallback"]
---

# 3cd20dc8: Hub semgrep rule frontend-token-storage.yml is silently inactive — gate looks in scripts/rules, file ships in hooks/rules

## What was observed

`plugin-dist/hooks/scripts/nodejs-security-stop-gate.py:52-53` computes
`_HUB_RULES_DIR = dirname(realpath(__file__)) + "/rules"`, i.e.
`…/hooks/scripts/rules/`. The rule file actually ships at
`plugin-dist/hooks/rules/frontend-token-storage.yml` (sibling of `scripts/`,
not inside it). Verified on the deployed tree:
`~/.claude/skills/mainframe/hooks/scripts/rules` — does not exist;
`~/.claude/skills/mainframe/hooks/rules/frontend-token-storage.yml` — exists.
`_hub_rule_configs()` (lines 56-58) returns `[]` when the dir is missing, so
the mismatch is silent.

## Why it is a problem

The custom localStorage/sessionStorage token-storage check — added precisely
because `p/security-audit` does not cover it (script header, lines 22-24) —
has never fired. A security gate believed to be active is dark, and the silent
`[]` fallback masks it. Same class as "test fixture must mirror real
side-effects": the guard degrades gracefully where loud failure was wanted.

## Why it is not a duplicate

No existing ticket mentions `frontend-token-storage`, `_HUB_RULES_DIR`, or the
hub rules dir (checked `rg -il` over `docs/tickets/`).

## What probably needs to be done

1. Decide the canonical location per the neutral-core layout (ADR 0085): rules
   are detector data → `core/gates/rules/`, rendered next to whatever layout
   the path computation expects. Then EITHER fix the path computation to
   `…/hooks/rules/` (one `dirname` higher) OR move the file into
   `scripts/rules/` — one change, not both.
2. Add a regression test that the gate actually picks up the hub rule file
   (e.g. `_hub_rule_configs()` returns exactly one path on the real tree).
3. Consider a loud note (not silent `[]`) when the rules dir is expected but
   missing — the silent fallback is what hid this.

Activating a previously-dark semgrep rule changes gate behavior (new possible
blocks on frontend diffs) — land it as its own change with its own smoke, NOT
inside the wave-1 zero-behavior-change migration. That is why this is a ticket
and not an inline fix.

## Acceptance criteria

- A test proves `frontend-token-storage.yml` is found and passed to semgrep
  (`--config` includes it) on the deployed layout.
- The rules location matches the neutral-core layout and is covered by the
  render manifest + golden `--check`.
- One manual probe: a diff introducing `localStorage.setItem('token', …)`
  trips the gate.

## Sources

- `plugin-dist/hooks/scripts/nodejs-security-stop-gate.py:22-24,52-63`
- `plugin-dist/hooks/rules/frontend-token-storage.yml`
- Memory: `semgrep-yaml-metavariable-regex-binding` (rule authoring caveats)
- ADR 0085 / `docs/design/neutral-core.md` §5 (wave-1 gates slice)

## Resolution (2026-07-08)

**Implementer:** autonomous session (Fable 5)
**Commits:** `2cc3969eea7625a79b94bb9b41a174b127f3f345`
**Summary:** `_HUB_RULES_DIR` now joins against the PARENT of the scripts dir
(`hooks/rules` / `core/gates/rules` are siblings of `scripts`/`detectors`);
fix landed in the core source and rendered.
**Claims to verify on audit:**
- `python3 tools/test_hub_semgrep_rules.py` — 3/3 (source layout, config
  list, rendered layout).
- `semgrep --config plugin-dist/hooks/rules/frontend-token-storage.yml` on a
  `localStorage.setItem("authToken", …)` bait file → 1 finding (verified live).
- `python3 tools/render_core.py --check` — in sync.
