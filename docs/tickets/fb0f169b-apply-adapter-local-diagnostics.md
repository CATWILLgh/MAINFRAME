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

The existing DEV implementation is also uneven: Claude Code uses the legacy
`install.sh --dev` links, while the other adapters already carry projected
event producers but do not have complete, separately managed activation and
feedback resources.

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

## What probably needs to be done

- Add explicit adapter-local activation resources to the release contract.
- Observe current event and feedback state without treating a database path as
  consent.
- Package and activate `harness-feedback` independently for each adapter.
- Preserve existing databases and reports when collection is disabled.
- Prepare and journal the changes through the same atomic apply boundary as the
  environment and MCP plan.
- Enforce `0700` directories and `0600` sensitive local files.

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
