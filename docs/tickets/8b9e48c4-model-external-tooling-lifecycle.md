---
id: 8b9e48c4
title: Model external tooling prerequisites in the lifecycle manager
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: ["#40f67f95"]
tags: ["tui", "tooling", "prerequisites", "package-manager"]
---

# 8b9e48c4: Model external tooling prerequisites in the lifecycle manager

## What was observed

The release manifest now covers every file shipped by MAINFRAME, but `install.sh` also detects or installs `ruff`, `pip-audit`, `semgrep`, `osv-scanner`, `oxlint`, `dependency-cruiser`, `knip`, and `fallow`. These machine-level prerequisites are not release payload files and are not represented in the read-only lifecycle model.

## Why it is a problem

The TUI can accurately describe complete release contents but cannot yet report whether optional security and quality hooks are operational. Calling that state full `install.sh` replacement parity would hide silent hooks and platform/package-manager differences.

## Why it is not a duplicate

- [#40f67f95](40f67f95-complete-release-manifest-for-tui.md) covers immutable release contents.
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers safe filesystem execution.

This ticket covers discovery, user choice, and installation policy for external tools that are neither release files nor ordinary configuration resources.

## What probably needs to be done

- Define typed prerequisite capabilities separately from artifacts and mutable configuration resources.
- Record which adapter features become inactive when a tool is absent.
- Add read-only detection for supported operating systems and package managers.
- Let the user choose optional tooling explicitly before any package-manager or network action.
- Move version policy away from unpinned `latest` installs and define update behavior.

## Acceptance criteria

- The TUI shows each optional prerequisite, current availability, affected functionality, and proposed action.
- A missing optional tool never appears as a fully operational hook.
- No package-manager or network command runs without explicit confirmation and a visible exact plan.
- macOS and Linux fixtures cover present, absent, unsupported, failed-install, and update cases.
- Full `install.sh` replacement parity is not claimed until this inventory is complete.

## Sources

- `install.sh:534`
- `install.sh:568`
- `install.sh:603`
- `install.sh:607`
- `install.sh:674`
- `install.sh:680`
- `tools/build_release.py`
