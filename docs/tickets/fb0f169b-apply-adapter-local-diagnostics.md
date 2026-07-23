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

The category-first TUI records separate drafts for local diagnostic events and
`harness-feedback`. Those choices now enter the typed lifecycle and reviewed
application request as exact per-adapter semantic intents, and the combined
preview renders the lifecycle result rather than reconstructing it locally.
Configured diagnostics are still explicitly non-executable and preparation
rejects them before executor resources open.

Bundle schema version 4 and the dormant `exact-json-document` strategy now
provide the release and preparation foundation. The contract authenticates a
strict schema-v1 exemplar, requires separate runtime desired bytes, reserves
the complete adapter-local `mainframe/diagnostics.json` target, rejects
overlapping claims, compares JSON semantically, and prepares private `0600`
publication through the existing configuration journal. No adapter manifest
used to advertise the resource, so the foundation could not prove that a
release carried per-adapter activation documents.

All four adapter manifests now advertise a dormant exact resource backed by
the same canonical disabled exemplar. Antigravity correctly targets its runtime
data root rather than its separate configuration root. Static TUI startup and
unconfigured requests skip all exact diagnostic targets; configured
application review scopes observation to the selected adapters only. The TUI
still presents this state explicitly as a draft, does not yet hand the final
request to application review, and the lifecycle execution guard remains in
place. Therefore packaging cannot write or activate diagnostics.

The configuration transaction now has the missing low-level removal primitive.
Exact documents use an explicit present-or-absent desired state, omission
leaves a resource untouched, and journal schema version 3 can recover or roll
back an atomic removal without staging an empty file. Removal is limited to the
observed activation document and does not delete databases, reports, or
feedback history. The lifecycle guard remains because the TUI and lifecycle
still need to map disable, adapter deselection, and complete uninstall to that
primitive deliberately.

The existing DEV implementation is also uneven: Claude Code uses the legacy
`install.sh --dev` links, while the other adapters already carry projected
event producers but do not have complete, separately managed activation and
feedback resources. Event and feedback writers now fail closed behind the
versioned activation document and protect newly written data with private
permissions; those writers are not yet activated by an executable TUI plan.

## Why it is a problem

The screen is intentionally honest about being preview-only, but it cannot
replace `--dev` until the desired state can be observed, safely applied,
disabled without deleting data, and restored independently for every selected
adapter.

## Why it is not a duplicate

Existing runtime-state work covers bounded retention after data exists, while
this ticket owns installer observation, activation, and adapter-local delivery.
The legacy Claude Code symlink decision is also narrower than the release and
TUI contract across every adapter.

## What remains to be done

- Connect the final TUI request to request-aware application review.
- Connect exact runtime intent to lifecycle preparation without treating the
  release exemplar or a database path as consent.
- Package and activate `harness-feedback` independently for each adapter.
- Preserve existing databases and reports when collection is disabled.
- Map deselection, disable, and complete uninstall to explicit exact-document
  removal intents at the lifecycle boundary.
- Cover those lifecycle transitions together with update and re-enablement;
  the lower configuration executor already covers atomic removal and recovery.

## Acceptance criteria

- The two TUI choices produce exact per-adapter intents and executable plan
  operations for every selected environment.
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
- `core/gates/detectors/_hooklib.py:343`
- `dev/skills/harness-feedback/feedback.py:57`
- `docs/installer-strategy.md`
