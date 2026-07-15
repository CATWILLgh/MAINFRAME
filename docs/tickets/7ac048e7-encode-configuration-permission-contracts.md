---
id: 7ac048e7
title: Encode configuration file and directory permission contracts
status: open
priority: medium
component: installer
discovered: 2026-07-15
discovered-from: ["#7a1c1d1d"]
tags: ["tui", "configuration", "permissions", "credentials", "security"]
---

# 7ac048e7: Encode configuration file and directory permission contracts

## What was observed

Release payload rows record source modes, but mutable resources do not declare the required mode of their destination file or parent directory. The credential seed is packaged as `0600`, while the read-only observer currently classifies any accessible regular `secrets.env` file as ready regardless of its destination mode.

## Why it is a problem

A future configuration executor could create or preserve a credential store with permissions broader than intended because the desired security property is absent from the resource contract. Observation also cannot warn about an already exposed credential file without a declared expected mode.

## Why it is not a duplicate

[#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) covers ownership and merge behavior. This ticket is limited to destination permission invariants for files and directories, especially credential material. [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers recoverable execution, not the desired mode data it consumes.

## What probably needs to be done

- Add explicit optional destination file and directory modes to the resource schema.
- Validate modes consistently in the Python writer and Go loader.
- Observe modes without reading secret content or following symbolic links.
- Define safe remediation rules that never broaden an existing credential path.
- Cover platform behavior on both macOS and Linux.

## Acceptance criteria

- The credential store contract declares `0600` for the file and an intentional mode for its parent directory.
- A broader existing mode is reported as needing attention without reading file content.
- Seed application creates missing paths with the declared modes and does not temporarily expose wider permissions.
- Python and Go contract validators reject malformed or contradictory mode declarations.
- macOS and Linux tests cover missing, exact, overly broad, inaccessible, and symbolic-link destinations.

## Sources

- `tools/build_release.py`
- `tools/release_contract.py`
- `internal/releasecontract/types.go`
- `internal/configuration/observer.go`
- `internal/hostfs/inspect_unix.go`
- `docs/tickets/7a1c1d1d-add-safe-plan-application.md`
