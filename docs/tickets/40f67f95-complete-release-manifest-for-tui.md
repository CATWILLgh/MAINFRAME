---
id: 40f67f95
title: Complete the release manifest before presenting a full TUI plan
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: []
tags: ["tui", "release", "bundle-v2", "manifest"]
---

# 40f67f95: Complete the release manifest before presenting a full TUI plan

## What was observed

The read-only terminal preview is composed from `installmanifest.StableComponents()`, which covers six stable artifacts from the legacy delivery layout. The autonomous Codex and OpenCode `bundle-v2` trees are not yet represented. The preview therefore carries a permanent development banner and names the excluded bundles instead of claiming to show a complete installation plan.

## Why it is a problem

Removing the banner now would make a partial plan look authoritative. The missing bundle inventory also prevents a packaged `mainframe` binary from resolving its source root independently of a repository checkout or the development-only `MAINFRAME_SOURCE_ROOT` override.

## Why it is not a duplicate

No existing ticket queue was present. This ticket is limited to complete release inventory and packaged source-root discovery; safe application of a plan is tracked separately in [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md).

## What probably needs to be done

- Generate the install manifest from complete, isolated Claude Code, Codex, and OpenCode release bundles.
- Define the installed release layout and resolve the active package root without depending on the current repository directory.
- Compare the generated inventory against the `install.sh` parity matrix and adapter isolation contracts.
- Replace the development-only source-root composition after the packaged layout is verified.

## Acceptance criteria

- Every shipped artifact for all three adapters appears once in the generated manifest with an owning component and source path.
- A packaged binary discovers the active release root without `MAINFRAME_SOURCE_ROOT` or a repository checkout.
- Read-only discovery and planning pass with the other adapter trees physically absent.
- The TUI can remove the partial-preview banner without omitting `bundle-v2` artifacts.
- Existing `mainframe plan` compatibility tests and all lifecycle tests remain green.

## Sources

- `internal/installmanifest/manifest.go:8`
- `cmd/mainframe/preview.go:28`
- `internal/tui/model.go:145`
- `adapters/codex/build_bundle.py`
- `adapters/opencode/build_bundle.py`
