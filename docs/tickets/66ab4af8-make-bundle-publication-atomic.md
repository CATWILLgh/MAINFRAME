---
id: 66ab4af8
title: Make generated bundle publication atomic after complete source validation
status: approved
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
- Apply the same publication contract to Claude Code, Codex, OpenCode, and
  Antigravity 2.x bundles.

## Acceptance criteria

- Any invalid nested source fails without changing the active bundle.
- Each lookup that starts from the public output name resolves through a fully
  materialized old or new bundle tree; no active tree is published file by file.
- Interruption at every publication step leaves either the old or fully validated new bundle recoverable.
- The output entry and its direct parent cannot be symbolic links. The remaining
  caller-supplied parent chain is an explicit trust boundary; managed cleanup
  never follows symbolic links inside a generation.

## Resolution

Resolved on 2026-07-19.

- Direct builders now materialize and validate a complete private sibling tree
  before one native no-replace or exchange rename publishes it.
- A persistent per-output lock serializes cooperating publishers. An atomically
  published journal binds the parent, old output, and staging directory to exact
  device and inode identities before the namespace transition.
- Recovery classifies only the closed set of journaled pre-commit,
  post-commit, retained-generation, and post-cleanup states. Unknown identities
  fail closed without deleting either generation. Private staging trees left by
  interruption before journal creation are reclaimed on the next locked build.
- The exchanged previous generation is renamed into a private retained slot
  instead of being deleted immediately. One prior generation survives until the
  next successful publication, so readers already holding its directory open
  are not invalidated by the commit that replaced it.
- The complete release builder calls pure adapter materialization inside its
  existing private release staging tree, so lock and journal metadata can never
  enter an indexed payload.
- Darwin uses `renameatx_np` with `RENAME_EXCL` or `RENAME_SWAP`; Linux uses
  `renameat2` with `RENAME_NOREPLACE` or `RENAME_EXCHANGE`. Unsupported systems
  and filesystems fail without a two-rename fallback.
- The guarantee applies to lookups that begin at the public output name and to
  cooperating publisher process recovery. A runtime that keeps a directory open
  across multiple later publications can outlive the single retained generation;
  separate reads spanning a commit can also observe two complete generations.
  Full Darwin power-loss durability is not claimed by this developer-build
  protocol.

## Sources

- `tools/bundle_publication.py`
- `tools/bundle_cleanup.py`
- `tools/bundle_rename.py`
- `tools/build_release.py`
- `tools/test_build_opencode_bundle.py`

## Audit

Approved on 2026-07-19 after an independent decision review.

- The reviewer reproduced and then verified fixes for direct-parent symbolic-link
  redirection, immediate invalidation of an open previous generation, and
  pre-journal staging leakage.
- The focused publication suites passed `14/14` and `8/8`; the complete Python
  suite, repeated Go suite, Go race detector, `go vet`, and render check also
  passed locally.
- No remaining High- or Medium-severity defect was grounded. The documented
  same-user, older pinned-reader, and Darwin power-loss limits remain deliberate
  follow-up boundaries rather than hidden guarantees.
