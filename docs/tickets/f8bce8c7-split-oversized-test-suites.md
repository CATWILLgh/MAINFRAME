---
id: f8bce8c7
title: Split oversized installer and projection test suites
status: open
priority: low
component: test-infrastructure
discovered: 2026-07-23
discovered-from: []
tags: ["maintainability", "tests", "file-size", "refactor"]
---

# f8bce8c7: Split oversized installer and projection test suites

## What was observed

The final size sweep found five pre-existing test files above the repository's
400-line limit:

- `internal/tui/model_test.go` — 410 lines;
- `internal/credentialcatalog/catalog_test.go` — 422 lines;
- `tools/test_build_codex_bundle.py` — 469 lines;
- `tools/test_build_opencode_bundle.py` — 481 lines;
- `tools/test_build_hub_page.py` — 535 lines.

The DEV feedback work changed narrow expectations in these suites but did not
create their existing structural size.

## Why it is a problem

Each file combines several independently testable concerns. That makes focused
maintenance harder and increases the chance that unrelated fixtures must change
together.

## Why it is not a duplicate

- [#50f7fc38](50f7fc38-split-test-build-opencode.md) split a different
  OpenCode projection suite and is already closed.
- [#15f992f2](15f992f2-build-hub-page-length-debt.md) owns the production hub
  page generator; this ticket owns the oversized test suite.
- [#aee3901b](aee3901b-build-codex-over-400-lines.md) owns the Codex generator,
  not its bundle tests.

## What probably needs to be done

- Split each suite along its existing fixture and behavior boundaries.
- Keep shared fixtures in one small helper module instead of copying them.
- Ensure the CI loop discovers every new `test_*.py` file.

## Acceptance criteria

- Every listed test file and extracted helper is at most 400 lines.
- Test counts and assertions remain unchanged.
- `go test ./internal/tui ./internal/credentialcatalog` and every affected
  Python suite pass.
- The full `tools/test_*.py` loop remains green.

## Sources

- `internal/tui/model_test.go`
- `internal/credentialcatalog/catalog_test.go`
- `tools/test_build_codex_bundle.py`
- `tools/test_build_opencode_bundle.py`
- `tools/test_build_hub_page.py`

## Re-occurrence noted (2026-07-27)

**Noticed during:** final size review of shared credential-reference tests
**Where:** `internal/credentialcatalog/catalog_test.go`
**Additional details:** The new shared-reference tests were moved into a
dedicated file, leaving the pre-existing catalog suite unchanged at 422 lines.
The oversized suite is now included in this ticket's inventory and acceptance
scope.
