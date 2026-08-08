---
id: 155cb2ff
title: TUI lacks release management and secret retirement that the CLI supports
status: open
priority: medium
component: tui
discovered: 2026-08-08
discovered-from: []
tags: ["tui", "release", "lifecycle", "parity", "secret-retire"]
---

# 155cb2ff: TUI lacks release management and secret retirement that the CLI supports

## What was observed

A parity audit between the TUI (`mainframe` with no args, entrypoint `cmd/mainframe/main.go:66` → `runInteractivePreview` → `internal/tui/`) and the CLI (20 commands declared in `mainframe capabilities --json`) found four CLI-only operations with no TUI screen:

1. **Release activation** — `release apply` (import-and-activate a local release, switch the `~/.local/bin/mainframe` symlink to a new binary). No TUI screen enumerates or activates releases.
2. **Rollback / cached-release switch** — `release apply` with the `activate-cached` operation. The TUI cannot return to a previously-cached release.
3. **Local release import** — `release review` + `release apply` against a freshly built source tree. The TUI cannot install a new release built from the repo.
4. **Secret retirement** — `credentials secret-retire prepare` / `apply`. The TUI credential menu (`internal/tui/credentials.go:58-99`) has no retirement option.

Evidence: `internal/tui/screens.go` enumerates all TUI screens; none reference release management. The only `release` mention in `internal/tui/` is `ReleaseID` in `credential_legacy_draft.go`, which belongs to the legacy-credential-transfer flow, not release lifecycle. The release subsystem lives entirely at `cmd/mainframe/release_command.go` and `cmd/mainframe/release_runtime.go` as CLI-only JSON-protocol commands (`command_specs.go:189-213`).

The TUI and CLI are otherwise at parity for adapter/MCP/credential lifecycle: both call the shared `application.Service.Review()` and `Service.ApplyConfirmed()` (`cmd/mainframe/preview.go:48-56`, `internal/lifecycle/`). Install, reconfigure, repair, and remove of adapters work identically through both interfaces. Conflict handling is also identical: `OperationConflict` makes `Applicable()` return false in both, blocking apply with no interactive override.

## Why it is a problem

The project's own "Done" definition (`AGENTS.md`: "it can be installed, reconfigured, repaired and removed without a repository checkout or a Python environment") implies the primary user-facing interface should cover the full cycle. A user who only uses the TUI cannot:

- update the `mainframe` binary when a new release is built;
- roll back to a known-good release after a bad activation;
- retire a secret after removing all references.

These are exactly the operations this session needed (binary update + rollback was required to apply the hook fix), and the TUI could not do any of them. The CLI worked, but a user relying on the TUI as the single interface is stuck.

## Why it is not a duplicate

- [#40f67f95](40f67f95-complete-release-manifest-for-tui.md) (closed) — covers release-manifest completeness in the TUI *preview*, not the ability to *activate* or *switch* releases. This ticket is about the missing release-management operations.
- [#8b9e48c4](8b9e48c4-model-external-tooling-lifecycle.md) (open) — covers modelling external tool prerequisites (`ruff`, `pip-audit`, etc.). Unrelated to release activation.
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) — covers safe filesystem execution of a plan. This ticket is about which operations the TUI exposes at all, not how safely they execute.

No existing ticket tracks "the TUI cannot perform release management or secret retirement".

## What probably needs to be done

- Add a TUI screen (or main-menu entry) for release management that lists cached releases and the active one, with review → confirm → apply for import-and-activate and activate-cached. Reuse the existing `releasecontract.Load` + `releasecache.Store` + `releaseactivation` path; only the TUI surface is missing.
- Add a secret-retire entry to the credential menu that calls the existing `credentials secret-retire prepare` / `apply` logic interactively.
- Decide whether release management belongs in the TUI at all, or is intentionally CLI-only for automation. If the latter, document the split explicitly so users know the TUI is not a complete interface. (requires verification: check whether the maintainer considers release activation an expert/automation-only operation.)

## Acceptance criteria

- A user can activate a freshly built local release through the TUI without dropping to the CLI, and verify the active binary changed.
- A user can roll back to a previously cached release through the TUI after a failed activation.
- A user can retire a secret through the TUI credential menu after removing all references.
- Or: an explicit documented decision that release management is CLI-only, with the TUI clearly marked as adapter/credential-only.

## Sources

- `cmd/mainframe/release_command.go`, `cmd/mainframe/release_runtime.go` — CLI release commands.
- `cmd/mainframe/command_specs.go:189-213` — release.review / release.apply declared CLI-only.
- `internal/tui/screens.go` — TUI screen enumeration (no release screen).
- `internal/tui/credentials.go:58-99` — credential menu (no retire option).
- `mainframe capabilities --json` — 20 CLI commands declared.
- `cmd/mainframe/preview.go:48-56` — shared `application.Service.Review()` path used by both TUI and CLI draft commands.
- Session evidence, 2026-08-08: applying the hook fix required `release apply` and `activate-cached`, neither available in the TUI.
