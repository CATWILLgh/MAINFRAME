---
id: f0fe90d0
title: Run the real Codex rule parser in continuous integration
status: open
priority: medium
component: ci
discovered: 2026-07-15
discovered-from: []
tags: ["codex", "permissions", "ci", "validation"]
---

# f0fe90d0: Run the real Codex rule parser in continuous integration

## What was observed

The Codex generator has a real `execpolicy` parser test, but it silently returns when the `codex` executable is absent. The CI workflow does not install Codex, while `install.sh --codex` always requests native validation.

## Why it is a problem

A generated `prefix_rule` syntax regression can pass CI and fail only on the user's machine during installation. Unit tests cover the expected text shape but do not establish compatibility with the actual parser.

## Why it is not a duplicate

No existing ticket covers Codex CLI availability or native permission validation in CI. The release-manifest and executor tickets concern installation content and lifecycle application instead.

## What probably needs to be done

- Verify the official Codex installation and version-pinning mechanism from current primary documentation.
- Install one reviewed Codex version in CI with caching where appropriate.
- Make the native parser test fail, rather than skip, in the dedicated CI job.
- Define a deliberate version-bump and compatibility-review policy.

## Acceptance criteria

- CI executes `codex execpolicy check` against the generated rules on every change.
- The job fails when Codex is unavailable or returns a mismatched decision.
- The installed version is explicitly pinned and updated through a documented review.
- Local tests may remain optional when Codex is absent, but CI cannot silently skip.

## Sources

- `.github/workflows/ci.yml:108`
- `tools/test_build_codex.py:277`
- `adapters/codex/build_codex.py:668`
- `install.sh:874`
