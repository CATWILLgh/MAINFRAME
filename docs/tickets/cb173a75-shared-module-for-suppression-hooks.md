---
id: cb173a75
title: Extract a shared marker/debug-residue module for the two suppression hooks (+ committed unit tests)
status: closed
priority: medium
component: hooks
discovered: 2026-06-03
discovered-from: []
tags: ["hooks", "refactor", "dry", "testing", "tech-debt"]
---

# cb173a75: Extract a shared marker/debug-residue module for the two suppression hooks (+ committed unit tests)

## What was observed

`MARKERS` and `DEBUG_RESIDUE` (the regex detector sets) are duplicated verbatim in `plugin-dist/hooks/scripts/scan-suppression-markers.py` (PostToolUse note) and `plugin-dist/hooks/scripts/stop-gate-suppression-markers.py` (Stop gate). The stop-gate's own docstring already flags it: *"marker AND debug-residue definitions are duplicated … keep in sync. A shared module is the cleaner refactor — deferred so the two hooks can be installed and tested independently."* ADR 0070 (debug-residue addition) doubled the duplicated surface.

The regexes are module-locals inside standalone scripts invoked by path under a bare `python3` — they are **not importable**, so there is **no committed unit-test cover**. Both hooks are validated only by ephemeral probes (20 probes in ADR 0070, all green), which leave zero regression cover: the next edit to `\bdd\s*\(` or any pattern has nothing to catch a break.

## Why it is a problem

1. **Duplication / drift** — a regex fix or new pattern in one hook silently diverges from the other. DRY violation across two files that must stay byte-identical.
2. **Untested validator logic** — ADR 0069 / CLAUDE.md mandate TDD for validator-class logic: "covered by a test before declare-done". These regex detectors are exactly that, yet have no committed test. This is the deferred TDD debt recorded in ADR 0070, surfaced here rather than left silent.

The two problems share one fix: a shared module makes the regexes importable, which is precisely what makes them unit-testable. Module and tests land together.

## Why it is not a duplicate

This is the shared-module refactor the stop-gate `NOTE` explicitly deferred. The precondition it named ("install and test the two hooks independently first") is now met — both are installed and probe-tested. No existing ticket covers it.

## What probably needs to be done

1. Extract `MARKERS`, `DEBUG_RESIDUE`, the extension sets, and the shared scan helpers (`_added_markers`, `_markers_in`, `_ext`, `CODE_EXTENSIONS`, `_SELF_FILES`) into one importable module co-located in `plugin-dist/hooks/scripts/` (stdlib only; resolve the import mechanism given hooks run as path-invoked standalone scripts — sibling import via `sys.path.insert(0, dirname(__file__))`, or `importlib`).
2. Both hooks import from it; delete the duplicated definitions; remove the "keep in sync" NOTE.
3. Add **committed unit tests** for the detector set: per-language catch + 0-FP (the 20 ADR-0070 probes become assertions). Handle the test file containing debug patterns as test data — add it to `_SELF_FILES`, or place tests outside `CODE_EXTENSIONS` scan scope.
4. Decide where hub-internal Python tests live + how they run (no harness exists today — `requires verification`: may need a minimal `tools/`-style runner).

## Acceptance criteria

- Single source of `MARKERS` + `DEBUG_RESIDUE`; both hooks import it; no duplicated regex blocks remain.
- Committed unit tests cover catch + 0-FP per language; reproduce the ADR-0070 probe matrix as assertions; tests pass locally.
- Both hooks still pass their probes after the refactor (no behavioural regression).

## Sources

- `plugin-dist/hooks/scripts/scan-suppression-markers.py`, `plugin-dist/hooks/scripts/stop-gate-suppression-markers.py` (the duplication + the deferral NOTE).
- `docs/decisions/0070-debug-residue-detection-hooks.md` (recorded TDD debt), `docs/decisions/0069-hardened-testing-doctrine.md` (TDD mandate).
- `docs/layers/decision-tree.md` §C (disposition), §B Recipe M3 (consolidate duplicated logic).

## Resolution (2026-06-03)

**Implementer:** main agent. **Commits:**
`a17c83e189a22a41af0f93dd70b23c9c482a2f27` (refactor + chokepoint),
`dfbb86172623bc31794023e1582f2a59c82dfca6` (tests). Phase 1 of the hook
shared-lib refactor (plan:
`~/.claude/plans/MAINFRAME/2026-06-03-hook-shared-lib-refactor.md`).

**Summary:** Extracted `_markers.py` (MARKERS + DEBUG_RESIDUE — the duplicated sets) and `_hooklib.py` (shared scaffolding) into `plugin-dist/hooks/scripts/`. The suppression pair now imports from them; the "keep in sync" NOTE and the duplicated blocks are gone. Committed unit tests added: `tools/test_markers.py` (4) + `tools/test_hooklib.py` (7). Import-failure chokepoint added (SessionStart-in-plugin + on-edit) so the shared-lib SPOF degrades to a LOUD signal, not silent gate-disable.

**Claims to verify on audit:**
- `MARKERS`/`DEBUG_RESIDUE` defined once (in `_markers.py`); no duplicated copy remains in either suppression hook.
- 20 marker/debug-residue probes pass identically post-migration (behaviour preserved).
- 11 unit tests pass: `python3 tools/test_markers.py && python3 tools/test_hooklib.py`.
- Broken `_hooklib.py` produces a loud note from both smoke-checks (verified this session).

**Note:** the broader refactor (Phase 2 security/deps pairs, Phase 3 remainder) continues separately; this ticket covered only the suppression-pair shared module + its tests, which are done.
