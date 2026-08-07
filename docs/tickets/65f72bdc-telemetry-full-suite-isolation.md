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

## Re-occurrence noted (2026-08-05)

**Noticed during:** ZCode writable-subagent lifecycle verification
**Where:** Sanitized full `python3 -m pytest -q --tb=short` run
**Additional details:** The same Codex and OpenCode telemetry tests failed in
the complete 808-test process while 803 tests, all ZCode-focused checks, and
the complete Go suite passed. No user credential variables were forwarded to
the test process.

## Re-occurrence noted (2026-08-07)

**Noticed during:** Verifying the `hook_config.py` bundle fix (separate change,
zcode-desktop adapter only — does not touch telemetry or release build).
**Where:** Full `python3 -m pytest tools/` run; confirmed pre-existing via
`git stash` on a clean tree (failures reproduce without the fix).
**Additional details:** Both telemetry tests above still fail in the full
suite. A third test now also fails alongside them with the same
`subprocess.CalledProcessError` signature, but on a different step —
`tools/test_build_release.py::test_build_creates_complete_indexed_release_and_executable_layout`
fails at `mainframe draft review` (exit 1), not at telemetry assertions. That
release-build failure may share a root cause with the telemetry isolation issue
(process-state or build-pipeline state leaking across tests in the full suite)
or may be a distinct problem; bundled here pending triage because all three
failures surface together only in the full-suite process and pass when run
focused on a clean tree.
