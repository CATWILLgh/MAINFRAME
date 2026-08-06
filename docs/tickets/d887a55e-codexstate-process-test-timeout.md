---
id: d887a55e
title: Make the Codex descendant-cancellation test reliable under full-suite load
status: open
priority: medium
component: codexstate
discovered: 2026-08-05
discovered-from: []
tags: ["codex", "process-lifecycle", "tests", "flake"]
---

# d887a55e: Make the Codex descendant-cancellation test reliable under full-suite load

## What was observed

`TestAppServerClientKillsDescendantsOnInspectionCancellation` failed in two consecutive `go test ./... -count=1` runs because its fake Codex process did not publish `codex.ready` within the fixed two-second deadline. The unchanged package passed `go test ./internal/codexstate -count=3`, so the failure currently appears sensitive to full-suite load rather than deterministic application behavior.

The test and implementation were last changed before the ZCode adapter work, and the current diff does not touch `internal/codexstate`.

## Why it is a problem

A load-sensitive regression gate makes the repository-wide result nondeterministic. It can hide a real process-lifecycle defect or block unrelated releases even when the focused contract is healthy.

## Why it is not a duplicate

No existing ticket records this `codex.ready` publication timeout or the difference between focused and repository-wide execution.

## What probably needs to be done

- Determine whether the child process is delayed, never started, or blocked before publishing readiness when Go packages run concurrently.
- Replace wall-clock readiness assumptions with a deterministic synchronization boundary where possible.
- Keep the cancellation deadline assertion strict; do not merely increase every timeout without identifying the delayed step.

## Acceptance criteria

- The test passes repeatedly under the same concurrency used by `go test ./...`.
- A deliberately broken descendant cleanup still fails the test.
- Focused and repository-wide runs exercise the same observable cancellation contract.

## Sources

- `internal/codexstate/app_server_process_unix_test.go:14`
- Full-suite runs on 2026-08-05: two failures waiting for `codex.ready` after two seconds.
- Focused run on 2026-08-05: `go test ./internal/codexstate -count=3` passed.

## Re-occurrence noted (2026-08-06)

**Noticed during:** Full-suite verification of the host-requirement classification change
**Where:** `TestAppServerClientKillsDescendantsOnInspectionCancellation`, same two-second
`codex.ready` window
**Additional details:** Third sighting, and the pattern is now consistent rather than
suspected: `go test -count=1 ./...` failed, `go test -count=1 ./internal/codexstate` alone
passed immediately afterwards on the same tree. The failure therefore depends on parallel
package load, not on any change under test — but it does mean an unrelated change cannot get
a clean whole-suite run on this machine without a second targeted run to explain the red.
Priority unchanged; the practical cost is that it teaches contributors to skim past a red
full-suite result, which is exactly how the `curl-requests` drift survived two days.
