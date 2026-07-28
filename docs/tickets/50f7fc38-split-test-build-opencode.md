---
id: 50f7fc38
title: tools/test_build_opencode.py exceeds the 400-line rule after the agents-slice additions
status: closed
priority: low
component: tools
discovered: 2026-07-08
discovered-from: []
tags: ["code-quality", "tests", "refactor"]
---

# 50f7fc38: tools/test_build_opencode.py exceeds the 400-line rule after the agents-slice additions

## What was observed

The `length-quality-note` Stop hook flags `tools/test_build_opencode.py` at
435 lines (limit 400). The overflow came with the ADR 0085 agents slice: the
contract-form fixtures plus the new `test_real_repo_agents_match_committed_goldens`
golden test.

## Why it is a problem

The hub enforces the 400-line rule on every other project; its own tooling
should comply. A 435-line hand-rolled-runner test file is also two suites in
one: agent projection (fixtures, prose rewrites, enrich, goldens) and
config/permission/MCP merge mechanics.

## Why it is not a duplicate

- [#e43819ea](e43819ea-length-gate-non-python-function-length.md) — gate
  language-coverage gap, unrelated.
- [#98d286b1](98d286b1-detector-functions-over-60-lines.md) — detector
  function length, unrelated file.

## What probably needs to be done

Split along the natural seam: `test_build_opencode_agents.py` (agent
projection + goldens) and `test_build_opencode.py` (permissions, MCP, config
merge, main). Both need pyyaml — update the CI stdlib-loop exclusion list
(exact-filename matches in `.github/workflows/ci.yml`) and add the new file
to the pyyaml test section. Deferred out of the agents slice deliberately:
the reviewer pass was mid-flight on this file's `file:line` refs.

## Acceptance criteria

- Both files under 400 lines; combined test count unchanged (27) and green.
- CI runs both after the pyyaml install; stdlib loop excludes both.

## Sources

- Stop-hook advisory, 2026-07-08
- `tools/test_build_opencode.py`, `.github/workflows/ci.yml`

## Resolution (2026-07-08)

**Implementer:** autonomous session (Fable 5)
**Commits:** `c06a7bf0e0c3eb0c6483302f6856e04298d2d460`
**Summary:** The suite was split along the agent-projection/config-merge
seam. `tools/test_build_opencode.py` retained the agent tests, while the new
`tools/test_build_opencode_config.py` received permission, MCP, config-merge,
and config-facing `main()` tests; shared fixtures remain imported rather than
duplicated. The cited commit is pure test motion.
**Claims to verify on audit:**
- `tools/test_build_opencode.py`: 292 lines, 13/13 tests pass.
- `tools/test_build_opencode_config.py`: 184 lines, 14/14 tests pass.
- Combined: 27/27 passes, matching the pre-split total.
- `.github/workflows/ci.yml`: stdlib "Hook test suite" loop excludes both
  filenames; "OpenCode projection generator tests" step runs both files.
- No assertion, fixture value, or module-under-test line changed in the cited
  commit.
