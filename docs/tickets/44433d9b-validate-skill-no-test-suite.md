---
id: 44433d9b
title: validate-skill.py has no test suite — root retargeting verified only empirically
status: closed
priority: low
component: tools
discovered: 2026-07-08
discovered-from: []
tags: ["validators", "test-coverage", "neutral-core"]
---

# 44433d9b: validate-skill.py has no test suite — root retargeting verified only empirically

## What was observed

While retargeting the validator to `core/skills` (ADR 0085 skills slice,
commit `adbe1a2`), no `tools/test_validate_skill.py` existed. The change
(LIVE_ROOTS/SUMMARY_ROOTS split, DEAD-SUPP byte-code exclusion) was verified
by manual probes: `--session-start` line count, `--from-hook` payloads across
all three roots, `--all` run. Every other hub tool (`render_core`,
`build_opencode`, `build_hub_page`, hooks) has a committed suite.

## Why it is a problem

The validator guards skill-budget contracts (token/line caps, frontmatter
completeness) that gate global delivery. Its behaviour is pinned only by CI
running `--all` on the current corpus — a rule regression that happens to
pass on today's skills (e.g. the root-split trap the slice reviewer named:
one wrong tuple silently drops live validation of render edits) would not
surface.

## Why it is not a duplicate

`rg -l 'validate-skill' docs/tickets/` matches only unrelated tickets
(code-audit naming, emphasis sweep). First ticket about validator test
coverage.

## What probably needs to be done

1. `tools/test_validate_skill.py` (stdlib-runner style like the other suites,
   run in CI after pyyaml install): fixture skill trees exercising each rule
   (token/line caps, DEPTH, DESC caps, DEAD-SUPP incl. `__pycache__`
   exclusion) plus mode tests: `--from-hook` accepts all three LIVE_ROOTS and
   ignores outside paths; `--all`/`--session-start` list SUMMARY_ROOTS only.
2. Wire into `.github/workflows/ci.yml` next to the other pyyaml suites.

## Acceptance criteria

- Suite red if LIVE_ROOTS loses the render root or SUMMARY_ROOTS double-lists
  it; green on the current corpus.
- CI runs the suite.

## Sources

- `tools/validate-skill.py`, commit `adbe1a2`
- Skills-slice review 2026-07-08 (objection 1: root-split trap)

## Resolution (2026-07-08)

**Implementer:** autonomous session (Fable 5)
**Commits:** `f4f4ef8fbf49b0403c0ed1f7445a73131a29b362`
**Summary:** `tools/test_validate_skill.py` — 10 tests pinning all 13 rule ids
(FM-PARSE/FM-REQUIRED/NAME-FMT/NAME-DIR/DESC-LEN/DESC-WHEN-LEN/BODY-TOKENS/
BODY-LINES/DEPTH/FORMAT/SUPP-LINES/DEAD-SUPP incl. byte-code-cache exclusion)
plus the LIVE_ROOTS/SUMMARY_ROOTS split; wired into CI after validator deps.
**Claims to verify on audit:**
- `.venv/bin/python3 tools/test_validate_skill.py` — 10/10.
- Root-split guard: removing a root from `LIVE_ROOTS` or double-listing in
  `SUMMARY_ROOTS` turns `test_live_roots_accept_three_and_reject_outside` red.
- CI has a "Skill validator tests" step after `pip install tiktoken pyyaml`.
