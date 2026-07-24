---
id: fb0f169b
title: Apply and observe adapter-local diagnostics from the TUI
status: closed
priority: medium
component: installer-tui
discovered: 2026-07-22
discovered-from: []
tags: ["diagnostics", "telemetry", "feedback", "lifecycle", "privacy"]
---

# fb0f169b: Apply and observe adapter-local diagnostics from the TUI

## What was observed

The category-first TUI records a `DEV` draft and exposes `harness-feedback`
only as an optional capability inside it. That hierarchy now enters the typed
lifecycle and reviewed application request as exact per-adapter semantic
intents, and the combined preview renders the lifecycle result rather than
reconstructing it locally.
Request-scoped application review now turns those intents into exact prepared
configuration mutations. Static TUI startup still omits activation inspection,
but the final screen now sends the complete request through application review
and renders its request-scoped semantic plan.

Bundle schema version 5 and the dormant `exact-json-document` strategy now
provide the release and preparation foundation. The contract authenticates a
strict schema-v1 exemplar, requires separate runtime desired bytes, reserves
the complete adapter-local `mainframe/diagnostics.json` target, rejects
overlapping claims, compares JSON semantically, and prepares private `0600`
publication through the existing configuration journal. Optional install units
carry the typed `dev.harness-feedback` feature identifier.

All four adapter manifests now advertise a dormant exact resource backed by
the same canonical disabled exemplar. Antigravity correctly targets its runtime
data root rather than its separate configuration root. Static TUI startup
skips all exact diagnostic targets. Final application review inspects selected
adapters only when their `DEV` state was configured, plus registry-backed
managed adapters that are being deselected. Foreign and selected-but-
unconfigured adapters remain outside the exact-document scope. The TUI retains
the reviewed plan behind a read-only interface, preserves the separate MCP
onboarding and credential summary, and invalidates the retained plan when the
user leaves or retries review. Its global Apply action remains disabled under
the separate executor activation ticket.

The configuration transaction now has the missing low-level removal primitive.
Exact documents use an explicit present-or-absent desired state, omission
leaves a resource untouched, and journal schema version 3 can recover or roll
back an atomic removal without staging an empty file. Removal is limited to the
observed activation document and does not delete databases, reports, or
feedback history. The lifecycle now maps configured choices for selected
adapters: either enabled feature publishes the complete document, while both
disabled features remove it. An unconfigured selected adapter remains
untouched, while deselection and complete uninstall remove activation only for
registry-backed managed adapters. Host-incompatible installations are
preserved.

All four release bundles now carry an adapter-local feedback receiver behind
the optional feature unit. Claude Code uses a separate namespaced DEV plugin;
Codex, OpenCode, and Antigravity use only their own skill roots. The legacy
`install.sh --dev` path migrates only the exact old repo-owned Claude symlink
and preserves foreign paths. Event and feedback writers fail closed behind the
versioned activation document and protect newly written data with private
permissions; the TUI still cannot apply the reviewed plan.

## Why it was a problem

The screen is intentionally honest about being preview-only. It now observes
and prepares the desired state safely, but it cannot replace `--dev` until that
reviewed state can be applied, disabled without deleting data, and restored
independently for every selected adapter.

## Why it is not a duplicate

Existing runtime-state work covers bounded retention after data exists, while
this ticket owns installer observation, activation, and adapter-local delivery.
The legacy Claude Code symlink decision is also narrower than the release and
TUI contract across every adapter.

## Resolution (2026-07-24)

The request-scoped observer now distinguishes static startup from final review.
The lifecycle derives stable removal intents for managed deselected adapters,
including complete uninstall, without treating foreign or incompatible state
as owned. The application carries those intents into one reviewed executable
plan.

A real-filesystem Darwin test installs registry-owned Claude Code base and DEV
links plus an activation document, removes them through the journaled executor,
verifies that diagnostic history remains, and then re-enables the complete
state. The same test is compiled for native Linux. Existing executor tests
cover interrupted exact-document removal, rollback, repeated recovery, and
previous-release replacement. The empty ownership-registry encoding exposed by
the full uninstall was corrected from `null` to `[]`.

The public Apply action remains unavailable and is still governed by
[#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) and its remaining activation
gates.

## Acceptance criteria

- The `DEV` choice and its nested feedback choice produce exact per-adapter
  intents and executable plan operations for every selected environment.
- Feedback cannot be enabled or installed while `DEV` is disabled.
- An unselected adapter is neither inspected through another adapter nor
  changed.
- Enabling, disabling, re-enabling, update, recovery, and complete uninstall
  are covered at the lifecycle and executor boundaries.
- Disabling keeps existing diagnostic data unless the user separately chooses
  to clear it.
- A plain install creates no diagnostics directory or database.

## Sources

- `internal/tui/diagnostics.go`
- `internal/tui/model.go`
- `internal/diagnostics/plan.go`
- `internal/application/service.go`
- `cmd/mainframe/preview.go`
- `cmd/mainframe/diagnostics_lifecycle_integration_unix_test.go`
- `core/gates/detectors/_hooklib.py`
- `dev/harness-feedback-plugin/skills/harness-feedback/feedback.py`
- `docs/installer-strategy.md`
