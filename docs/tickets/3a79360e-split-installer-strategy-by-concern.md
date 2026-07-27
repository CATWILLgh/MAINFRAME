---
id: 3a79360e
title: Split the installer strategy by architectural concern
status: open
priority: low
component: docs
discovered: 2026-07-27
discovered-from: []
tags: ["documentation", "architecture", "maintainability"]
---

# 3a79360e: Split the installer strategy by architectural concern

## What was observed

`docs/installer-strategy.md` is 617 lines and combines runtime isolation,
diagnostics, MCP onboarding, credential handling, release storage, platform
support, and rollout sequencing. The central credential catalog change could
only keep its addition concise by moving details into ADR 0088.

## Why it is a problem

The file exceeds the repository's 400-line limit. Unrelated decisions are
harder to review independently, and future edits are more likely to append
contradictory rules instead of superseding the exact owner.

## Why it is not a duplicate

No existing ticket found by searches for `installer-strategy`, its title, or
its current line count tracks this documentation boundary.

## What probably needs to be done

- Preserve one short index that states the shared invariants.
- Move diagnostics, MCP, credential, release-storage, and platform details
  into focused normative documents or ADRs.
- Replace moved sections with links and verify that every current normative
  statement has exactly one owner.

## Acceptance criteria

- Every resulting source file is at most 400 lines.
- Runtime isolation and Apply safety invariants remain discoverable from the
  main strategy document.
- A link and contradiction audit finds no lost or duplicated normative rule.
- Documentation references and repository validators pass.

## Sources

- `docs/installer-strategy.md`
- `AGENTS.md` engineering file-size rule
