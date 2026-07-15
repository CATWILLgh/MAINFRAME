---
id: 33930a3b
title: Separate release catalog metadata from selectively downloaded payloads
status: open
priority: medium
component: installer-delivery
discovered: 2026-07-15
discovered-from: ["#40f67f95"]
tags: ["release", "delivery", "performance"]
---

# 33930a3b: Separate release catalog metadata from selectively downloaded payloads

## What was observed

`tools/build_release.py` currently assembles every adapter payload into one release directory. `internal/releasecontract/loader.go` then loads and verifies every indexed bundle before the TUI presents adapter choices. The index separates component manifests, but the current runtime still requires all payload bytes to be present locally.

## Why it is a problem

The intended delivery model downloads only the components selected by the user. Eager assembly and validation preserve correctness for the current local packaged preview, but they cannot support that delivery experience without changing the catalog/payload boundary.

## Why it is not a duplicate

- [#d3b15da9](d3b15da9-authenticate-release-publisher.md) covers authenticity of downloaded release material; this ticket covers selecting which material is downloaded.
- [#8b9e48c4](8b9e48c4-model-external-tooling-lifecycle.md) covers external programs managed by installation; this ticket covers MAINFRAME's own release payloads.

## What probably needs to be done

- Define a signed catalog containing enough component, dependency, resource, size, and digest metadata to render a selection before payload download.
- Fetch only the dependency closure of selected adapters into an immutable local release cache.
- Verify each fetched manifest and payload before it becomes eligible for planning or application.
- Keep the current complete local release builder as an offline/test fixture or add an explicit complete-release mode.

## Acceptance criteria

- Starting the TUI requires catalog metadata but not all adapter payloads.
- Selecting an adapter downloads only its dependency closure.
- Missing or tampered selected payloads fail closed before planning or application.
- Unit and integration tests prove that an unselected adapter payload is neither requested nor required.

## Sources

- `tools/build_release.py`
- `internal/releasecontract/loader.go`
- Phase 9 independent architecture review, 2026-07-15
