---
id: 003
title: hooks.md §1.7 stale hook-count claim ("16 hooks configured = 2+3+6+5")
status: closed
priority: low
component: docs
discovered: 2026-06-11
discovered-from: []
tags: ["docs", "layers", "hooks", "count-drift"]
---

# 003: hooks.md §1.7 stale hook-count claim ("16 hooks configured = 2+3+6+5")

## What was observed
`docs/layers/hooks.md` line ~61 states: the installed CLI `/hooks` menu header *"16 hooks configured"*
equals the hub's own registrations *"(§2.1: 2+3+6+5)"*. That arithmetic no longer matches the live
tables: the §2.1 `Stop` and `PostToolUse` groups each list **7** scripts, not 6/5. Counting actual
command registrations in `plugin-dist/hooks/hooks.json` (2026-06-11) gives **26** across **9**
(event, matcher) groups — neither 16 nor 2+3+6+5. The `secret-commit-gate` addition (ADR 0079) brought
the `PreToolUse Bash` group to 4, widening the gap. The "16" counts some other CLI metric (grouping not
reverse-engineerable from the doc).

## Why it is a problem
A "current registrations = N" claim that is provably wrong erodes trust in the doc and in the §2.1 count
as a self-check. Low impact (prose side-note, not a behavioural spec), but it is a contradiction left in
a published layer doc (`docs/layers/` ships).

## Why it is not a duplicate

- [#001](001-agents-md-stale-plugin-migration.md) covered the agent-layer path
  and inventory after the same plugin migration; it did not cover hook
  registration arithmetic.
- [#b74495c2](b74495c2-decision-tree-stale-export-paths.md) covered retired
  artifact paths in placement guidance; it did not own the independently
  stale count in `docs/layers/hooks.md`.

## What probably needs to be done
- Ground-truth the real `/hooks` menu header against the installed CLI (dispatch `claude-code-guide`, or
  read the menu directly) — the running CLI is authority (the doc itself says so).
- Reconcile the §1.7 line with what "16/N configured" actually counts, or drop the fragile exact
  arithmetic and state a verifiable metric (e.g. "9 (event,matcher) groups / 26 command registrations").

## Acceptance criteria
- `hooks.md` no longer carries a self-contradicting count vs the §2.1 tables.
- Any stated number is verifiable against the installed CLI or `hooks.json`, with the source named.

## Sources
- `docs/layers/hooks.md:61` (claim) and `:156-164` (§2.1 tables, the contradicting current counts).
- `plugin-dist/hooks/hooks.json` — 26 command registrations / 9 groups measured 2026-06-11.
- ADR 0079 (`secret-commit-gate` registration that widened the gap).

## Resolution (2026-06-14)

**Implementer:** MAINFRAME docs actualization session
**Commits:** `13ebb7f920a58fca97ed23f054fdbc1c8d60df6c`
**Summary:** The fragile `16 = 2+3+6+5` statement was replaced with a
source-named count from the then-current `hooks.json`: 31 registrations across
7 of the 30 events. The count had grown from the 26 registrations observed
when the ticket was opened.
**Claims to verify on audit:**
- The cited commit removes the `16 hooks configured = 2+3+6+5` statement from
  `docs/layers/hooks.md`.
- The replacement names `hooks.json` as the registration source of truth.
- The replacement records `SessionStart` 4, `PreToolUse` 8, `PostToolUse` 8,
  `Stop` 8, and one each for `PermissionDenied`, `SubagentStart`, and
  `SessionEnd`, totaling 31.
- The §2.1 tables at that revision agree with the 8 `Stop` and 8
  `PostToolUse` registrations.
