---
id: fb0f169b
title: Apply and observe adapter-local diagnostics from the TUI
status: open
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
data root rather than its separate configuration root. Static TUI startup and
unconfigured requests skip all exact diagnostic targets; configured
application review scopes observation to the selected adapters only. The TUI
retains the reviewed plan behind a read-only interface, preserves the separate
MCP onboarding and credential summary, and invalidates the retained plan when
the user leaves or retries review. Its global Apply action remains disabled.
Therefore no user-facing TUI path writes or activates diagnostics yet.

The configuration transaction now has the missing low-level removal primitive.
Exact documents use an explicit present-or-absent desired state, omission
leaves a resource untouched, and journal schema version 3 can recover or roll
back an atomic removal without staging an empty file. Removal is limited to the
observed activation document and does not delete databases, reports, or
feedback history. The lifecycle now maps configured choices for selected
adapters: either enabled feature publishes the complete document, while both
disabled features remove it. Unconfigured requests remain untouched. Adapter
deselection and complete uninstall still need deliberate removal semantics
outside this section.

All four release bundles now carry an adapter-local feedback receiver behind
the optional feature unit. Claude Code uses a separate namespaced DEV plugin;
Codex, OpenCode, and Antigravity use only their own skill roots. The legacy
`install.sh --dev` path migrates only the exact old repo-owned Claude symlink
and preserves foreign paths. Event and feedback writers fail closed behind the
versioned activation document and protect newly written data with private
permissions; the TUI still cannot apply the reviewed plan.

## Why it is a problem

The screen is intentionally honest about being preview-only. It now observes
and prepares the desired state safely, but it cannot replace `--dev` until that
reviewed state can be applied, disabled without deleting data, and restored
independently for every selected adapter.

## Why it is not a duplicate

Existing runtime-state work covers bounded retention after data exists, while
this ticket owns installer observation, activation, and adapter-local delivery.
The legacy Claude Code symlink decision is also narrower than the release and
TUI contract across every adapter.

## What remains to be done

- Map adapter deselection and complete uninstall to explicit exact-document
  removal intents outside the selected-adapter diagnostics section.
- Cover those lifecycle transitions together with update and re-enablement;
  the lower configuration executor already covers atomic removal and recovery.

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
- `core/gates/detectors/_hooklib.py`
- `dev/harness-feedback-plugin/skills/harness-feedback/feedback.py`
- `docs/installer-strategy.md`
