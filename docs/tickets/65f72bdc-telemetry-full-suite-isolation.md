---
id: 65f72bdc
title: Isolate Codex and OpenCode telemetry tests from full-suite process state
status: open
priority: medium
component: testing
discovered: 2026-08-05
discovered-from: []
tags: ["telemetry", "codex", "opencode", "tests", "isolation"]
---

# 65f72bdc: Isolate Codex and OpenCode telemetry tests from full-suite process state

## What was observed

Two existing telemetry bundle tests fail only inside the complete `python3 -m pytest -q` process: their opted-in telemetry databases are not created. The exact tests pass together when run in a fresh focused process:

- `tools/test_build_codex_bundle_runtime.py::test_bundle_telemetry_uses_only_codex_local_state`
- `tools/test_build_opencode_bundle.py::test_bundled_plugin_writes_only_to_opted_in_opencode_telemetry`

The same full-suite failures were reproduced before and after the ZCode adapter's import-isolation corrections. The ZCode adapter does not select or install telemetry.

## Why it is a problem

Telemetry contract results currently depend on Python test collection or process state. That makes the repository-wide gate nondeterministic and can conceal a real cross-adapter state leak.

## Why it is not a duplicate

Existing telemetry tickets concern runtime activation and storage. None records the discrepancy between focused and full-suite execution for both Codex and OpenCode bundles.

## What probably needs to be done

- Identify the earlier test or imported module that changes the bundled detector or environment contract.
- Make each bundle test construct and execute its telemetry surface from isolated state.
- Add an order-reversal regression covering Codex and OpenCode telemetry builders.

## Acceptance criteria

- Both tests pass focused and in the complete suite.
- Reversing their collection order produces the same artifacts.
- Opt-out tests still prove that no telemetry database is created.

## Sources

- `tools/test_build_codex_bundle_runtime.py`
- `tools/test_build_opencode_bundle.py`
- Full and focused pytest runs on 2026-08-05.
