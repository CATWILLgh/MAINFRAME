---
id: 1772f506
title: Isolate adapter builder imports in the combined Python test suite
status: open
priority: low
component: tests
discovered: 2026-07-17
discovered-from: []
tags: ["python", "tests", "import-order", "ci"]
---

# 1772f506: Isolate adapter builder imports in the combined Python test suite

## What was observed

`python3 -m pytest tools` is order-dependent because several adapter test
modules import a different file under the same bare module name
`build_bundle`. In the observed order, the Codex bundle test received another
adapter's cached module and reported a missing `mainframe-hook.sh`. Running
`python3 tools/test_build_codex_bundle.py` alone passes, and the repository's CI
intentionally runs these scripts in separate processes.

## Why it is a problem

Developers cannot rely on ordinary combined Pytest collection as a local
regression command. The false failure can hide a real failure in later tests
and makes test behavior depend on import order rather than code state.

## Why it is not a duplicate

No existing ticket covers Python module-cache collisions between adapter
builder tests. This is separate from MCP release schema v2: the failure
reproduces in unrelated Codex projection tests and disappears when each script
runs in the isolated process used by CI.

## What probably needs to be done

- Load every adapter builder under a unique module name, matching the pattern
  already used by `tools/build_release.py`, or convert the adapters into
  unambiguous packages.
- Remove temporary `sys.path` mutations and bare `import build_bundle` calls
  from the affected tests.
- Keep direct script execution working because it remains the current CI
  contract.

## Acceptance criteria

- `python3 -m pytest -q tools` passes from a clean interpreter.
- Every affected test script still passes when executed directly.
- Test results remain identical regardless of collection order.

## Sources

- `tools/test_build_codex_bundle.py`
- `tools/test_build_opencode_bundle.py`
- `tools/test_build_claude_bundle.py`
- `tools/test_build_antigravity.py`
- `tools/build_release.py:32-44`
- `.github/workflows/ci.yml:45-135`
