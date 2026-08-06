---
id: 9e64c997
title: Requalify the Antigravity adapter for installed version 2.5.0
status: open
priority: medium
component: antigravity-2
discovered: 2026-08-05
discovered-from: []
tags: ["antigravity", "compatibility", "release-tests"]
---

# 9e64c997: Requalify the Antigravity adapter for installed version 2.5.0

## What was observed
The installed `/Applications/Antigravity.app` reports bundle identifier `com.google.antigravity` and version `2.5.0`. The current adapter contract accepts only `2.2.1`. As designed, the packaged release draft rejects Antigravity selection with `component "antigravity-2" does not satisfy its host requirement`.

This makes the environment-sensitive Antigravity branch of `python3 tools/test_build_release.py` red while the ZCode tests and the complete Go suite are green.

## Why it is a problem
Antigravity cannot be selected on the currently installed host until its behavior is requalified. The packaged cross-component test also cannot complete its Antigravity apply scenario on this machine, which reduces the breadth of the final release regression run.

## Why it is not a duplicate
No existing ticket covers Antigravity `2.5.0` compatibility. The ZCode host requirement is independently green and does not cause this rejection.

## What probably needs to be done
Run the Antigravity installed-contract probes against `2.5.0`, compare hook, plugin, skill, agent, memory, diagnostics, and MCP behavior with the pinned `2.2.1` contract, then add the version only if every required behavior still holds. Make the packaged lifecycle assertion hermetic enough that an unrelated system application update does not silently weaken or unpredictably break the test.

## Acceptance criteria
- Installed Antigravity `2.5.0` passes the adapter capability and native behavior matrix.
- The host requirement admits `2.5.0` only after the evidence is recorded.
- Antigravity projection and lifecycle suites pass without weakening assertions.
- `python3 tools/test_build_release.py` completes all three scenarios on a supported or hermetically simulated host.

## Sources
- `adapters/antigravity-2/compatibility.py`
- `internal/hostcompatibility/evaluate.go`
- `tools/release_draft_fixture.py`
- `tools/release_draft_assertions.py`

## Re-occurrence noted (2026-08-05)

**Noticed during:** ZCode writable-subagent lifecycle verification
**Where:** `python3 -m pytest -q tools/test_build_release.py`
**Additional details:** The ZCode install, customized-file preservation,
conflict, cleanup, and reinstall stages completed before the packaged suite
reached the already tracked Antigravity host rejection. The full Go suite and
focused ZCode/release-contract tests remained green.

## Re-occurrence noted (2026-08-06)

**Noticed during:** Widening managed-file apply capability beyond the credential store
**Where:** `tools/test_build_release.py::test_build_creates_complete_indexed_release_and_executable_layout`
**Additional details:** Second sighting, same shape: the packaged `draft review` invocation
exits 1 and the suite reports 2/3. Confirmed **not** caused by the change under test — the
failure reproduces with the change stashed. Practical cost recorded here because it repeated
the pattern from `d887a55e`: an unrelated change cannot get a clean run of this suite on a
machine without a qualifying Antigravity install, so every contributor has to re-derive that
the red is pre-existing. Worth considering whether this test should skip with a stated reason
when the host application is absent, rather than fail.
