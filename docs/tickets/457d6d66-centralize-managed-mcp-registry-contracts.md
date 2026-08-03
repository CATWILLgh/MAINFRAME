---
id: 457d6d66
title: Centralize managed MCP ownership registry contracts
status: closed
priority: low
component: mcp
discovered: 2026-07-29
discovered-from: ["#2e7c03de"]
tags: ["credentials", "mcp", "ownership", "architecture"]
---

# 457d6d66: Centralize managed MCP ownership registry contracts

## What was observed

`ScanManagedSecretReferences` enumerates the four current ownership registry
locations in `managedRegistryContracts`. Adapter publication receives registry
targets from release projections instead of consuming that list. The two paths
agree now, but a new adapter or a changed registry path can update publication
without updating the retirement scanner.

## Why it is a problem

Secret retirement promises to inspect every MAINFRAME-managed adapter copy.
Independent ownership lists can drift and make a future adapter invisible to
that safety check. The current four adapters are covered, so this is a
maintenance hazard rather than a present bypass.

## Why it is not a duplicate

- [#2e7c03de](2e7c03de-complete-central-credential-catalog-rollout.md) tracks
  completion and delivery of the central catalog. This ticket is limited to
  eliminating duplicate ownership of managed registry locations.

## What probably needs to be done

- Define one registry contract owned by `mcpconfiguration`.
- Make adapter planning and the scanner consume that contract, while retaining
  inspection of stale registries that are no longer in the active projection.
- Add an exhaustiveness test that fails when a secret-bearing adapter is added
  without a retirement-scanner contract.

## Acceptance criteria

- Registry paths and supported secret-bearing formats have one code owner.
- Adding or changing a managed registry requires one contract update.
- Tests prove every supported secret-bearing adapter is scanned even when its
  current projection is absent.
- Existing OpenCode, Antigravity, Claude Code, and Codex scanner tests remain
  green.

## Sources

- `internal/mcpconfiguration/managed_secret_references.go`
- `internal/mcpconfiguration/inspection.go`
- `internal/mcpconfiguration/antigravity_secret_ownership.go`
- `cmd/mainframe/credential_machine_runtime.go`

## Resolution

The release contract now exposes a sorted, caller-isolated registry inventory
derived directly from the same codec contracts that validate adapter
publication. The retirement scanner consumes that inventory instead of
maintaining a second list. Registry decoding remains in `mcpconfiguration`,
where the supported secret-bearing formats are validated and unknown formats
continue to fail closed.

Tier 1 tests prove the four supported adapter registries are returned once in a
stable order, callers cannot mutate the shared contract, absent active
projections do not prevent stale-registry inspection, and the existing
OpenCode, Antigravity, Claude Code, and Codex scan behavior remains green.
