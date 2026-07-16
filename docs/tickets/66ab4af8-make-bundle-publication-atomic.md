---
id: 66ab4af8
title: Make generated bundle publication atomic after complete source validation
status: open
priority: medium
component: bundles
discovered: 2026-07-15
discovered-from: []
tags: ["bundle-v2", "publication", "symlink", "recovery"]
---

# 66ab4af8: Make generated bundle publication atomic after complete source validation

## What was observed

`tools/build_release.py` already contains component-builder failures by
assembling and validating the complete release in a private sibling staging
directory before publication. Direct component-builder outputs do not all have
that guarantee. The OpenCode builder validates permission rules before touching
the output, but nested source-tree validation still happens inside later
`sync_tree()` calls. A direct bundle build can therefore fail after
`prepare_output_root()` has removed stale output and earlier sections have been
rewritten.

## Why it is a problem

A failed direct bundle build can leave a mixed output containing old and new
sections. The outer complete-release builder prevents that partial output from
becoming a published release, but direct consumers still lack the same
guarantee. A separate preflight traversal would narrow the window without
closing the race between validation and copying.

## Why it is not a duplicate

[#40f67f95](40f67f95-complete-release-manifest-for-tui.md) covers complete release inventory and package-root discovery. This ticket covers transactional publication of the generated bundle itself.

## What probably needs to be done

- Build every bundle into a private sibling staging directory.
- Validate the complete staged tree and manifest before publication.
- Replace the active bundle through a recoverable directory-swap protocol.
- Preserve the last valid bundle when staging, validation, publication, or cleanup fails.
- Apply the same publication contract to Claude Code, Codex, and OpenCode bundles.

## Acceptance criteria

- Any invalid nested source fails without changing the active bundle.
- Readers never observe a mixed old/new bundle.
- Interruption at every publication step leaves either the old or fully validated new bundle recoverable.
- Symbolic-link source and destination attacks cannot redirect writes outside the owned bundle root.

## Sources

- `adapters/opencode/build_bundle.py:169`
- `tools/bundle_sync.py:8`
- `tools/bundle_sync.py:52`
- `tools/build_release.py:143`
- `tools/test_build_opencode_bundle.py`
