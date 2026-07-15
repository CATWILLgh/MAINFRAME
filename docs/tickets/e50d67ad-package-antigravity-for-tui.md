---
id: e50d67ad
title: Package Antigravity as an installer TUI component
status: open
priority: medium
component: installer
discovered: 2026-07-16
discovered-from: []
tags: ["antigravity", "tui", "release", "bundle"]
---

# e50d67ad: Package Antigravity as an installer TUI component

## What was observed

The Antigravity adapter builds a self-contained plugin and `install.sh --antigravity-2` can install it. The immutable release builder still indexes only Claude Code, Codex, and OpenCode adapter bundles, so the packaged `mainframe` binary and TUI cannot select, observe, install, update, or remove Antigravity.

## Why it is a problem

After the Antigravity branch is integrated, two delivery paths expose different runtime sets. Without an explicit release component, users could reasonably interpret repository support for Antigravity as support in the new TUI even though it remains available only through the legacy installer.

## Why it is not a duplicate

- [#a6e1135a](a6e1135a-split-monolithic-installer.md) covers decomposing the legacy shell installer; it does not add Antigravity to the immutable release contract.
- [#bce23629](bce23629-live-antigravity-plugin-validation.md) covers live desktop activation after installation; it does not model packaged delivery or TUI lifecycle behavior.
- [#33930a3b](33930a3b-enable-selective-release-downloads.md) covers metadata-first download for already packaged components; Antigravity is not yet a release component.

## What probably needs to be done

- Add an Antigravity bundle builder that expresses the plugin tree, dependencies, target root, and ownership in the release contract.
- Add Antigravity to release assembly and the install model without coupling it to Claude Code state.
- Define read-only discovery and configuration observation for its plugin and persistent memory paths before exposing apply or removal.
- Preserve the separate live-application validation tracked by `bce23629` as an external readiness check.

## Acceptance criteria

- A built release contains one indexed Antigravity component with complete integrity metadata.
- The TUI can independently select Antigravity and accurately report its installed, missing, drifted, and externally unverified states.
- Planning Antigravity does not implicitly select Claude Code except through explicit shared dependencies.
- Apply and removal are exposed only after ownership-safe lifecycle contracts and regression tests exist.
- Existing Claude Code, Codex, OpenCode, legacy installer, and packaged-release tests remain green.

## Sources

- `tools/build_release.py:143-173`
- `adapters/antigravity-2/build_antigravity.py:245-330`
- `install.sh:924-1005`
- `docs/tickets/40f67f95-complete-release-manifest-for-tui.md`
