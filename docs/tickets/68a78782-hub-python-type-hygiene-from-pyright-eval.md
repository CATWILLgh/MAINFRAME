---
id: 68a78782
title: Hub Python type-hygiene improvements surfaced by the pyright LSP evaluation
status: open
priority: low
component: hooks
discovered: 2026-06-14
discovered-from: []
tags: ["python", "type-hints", "pyright", "code-quality"]
---

# 68a78782: Hub Python type-hygiene improvements surfaced by the pyright LSP evaluation

## What was observed

During the pyright LSP evaluation (`docs/research/lsp-pyright-evaluation.md`), running
pyright over the hub's own Python surfaced real (minor) hygiene gaps in working,
correct code:

1. **Missing `-> NoReturn` on `sys.exit()` wrappers.** `emit()` and `defer()` in
   `plugin-dist/hooks/scripts/path-validation.py:63,76` call `sys.exit()` but are
   annotated `-> None`. This is almost certainly a recurring pattern across the other
   hook scripts (each has a defer/emit helper). Consequence: a static type-checker
   cannot narrow control flow after those calls, producing cascading false
   "possibly-unbound / None" diagnostics (6 such on `path-validation.py` alone).
2. **Unused import.** `tools/test_memory_reminder.py:16` imports `time`, never used
   (ruff `F401`).
3. **(Optional, only if pyright becomes a layer)** test files load modules via
   `sys.path.insert(...)` + `importlib.util.spec_from_file_location(...)`. A type-checker
   cannot follow this, yielding ~36 false positives in `tools/` test files. Fixable with
   a `pyrightconfig.json` `extraPaths` entry + `assert spec and spec.loader` at the load
   sites — but only worth doing if pyright is adopted as a hub tool.

## Why it is a problem

Low severity — none of these are runtime bugs. `emit`/`defer` do exit correctly; the
unused import is cosmetic; the test-load pattern works. The value is twofold: (a) the
`NoReturn` annotations make intent explicit and are the standard fix for the cascading-FP
pattern any type-checker (or a future LSP layer) would hit; (b) removing the dead import
is trivial cleanliness. Per ESLint/Ruff-equivalent reasoning, unused imports and missing
control-flow annotations are accepted minor-quality findings, not noise.

## Why it is not a duplicate

No existing ticket matches (`rg -i 'noreturn|pyright|unused import' docs/tickets/` — empty).
Tickets 001-004 are about stale docs / emphasis sweep / telemetry — unrelated.

## What probably needs to be done

- Add `from typing import NoReturn` and annotate every `sys.exit()`-wrapper helper
  (`emit`, `defer`, and siblings) across `plugin-dist/hooks/scripts/*.py` as `-> NoReturn`.
  Verify each hook's existing smoke/test still passes.
- Remove the unused `time` import in `tools/test_memory_reminder.py`.
- Defer item 3 (pyrightconfig `extraPaths` + importlib asserts) until/unless the pyright
  LSP layer decision lands — it is only worth it if the hub adopts pyright.

## Acceptance criteria

- `pyright plugin-dist/hooks/scripts/` no longer reports `reportPossiblyUnboundVariable`
  / `reportOptional*` errors that trace to the `emit`/`defer` `NoReturn` gap.
- `ruff check tools/test_memory_reminder.py --isolated` is clean (no `F401`).
- Each touched hook's existing test (`tools/test_*.py`) still green.

## Sources

- `docs/research/lsp-pyright-evaluation.md` — the evaluation that surfaced these.
- `plugin-dist/hooks/scripts/path-validation.py:63` (`emit`), `:76` (`defer`).
- `tools/test_memory_reminder.py:16` (unused `time`).
