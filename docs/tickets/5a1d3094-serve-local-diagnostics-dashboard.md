---
id: 5a1d3094
title: Serve an on-demand local diagnostics dashboard
status: open
priority: low
component: mainframe-cli
discovered: 2026-07-22
discovered-from: ["#fb0f169b"]
tags: ["diagnostics", "dashboard", "localhost", "sqlite"]
---

# 5a1d3094: Serve an on-demand local diagnostics dashboard

## What was observed

`build_hub_page.py` already generates a self-contained static `hub.html` with a
telemetry panel. It is repo-oriented, embeds one database snapshot at build
time, and does not update while the page is open. The proposed product
experience needs an optional local page that can aggregate adapter-owned stores
and refresh while MAINFRAME is running.

## Why it is a problem

Rebuilding and reopening a static project file is not a durable end-user
diagnostics experience. Starting a permanent daemon immediately would add
unnecessary lifecycle, port, security, update, and uninstall risk before the
read model and adapter-local storage contract are complete.

## Why it is not a duplicate

- [#fb0f169b](fb0f169b-apply-adapter-local-diagnostics.md) owns diagnostic
  activation and storage. This ticket owns the optional read-only browser view.
- Runtime retention work owns storage limits, not presentation or local
  serving.

## What probably needs to be done

- Add `mainframe diagnostics serve` after adapter-local storage is implemented.
- Reuse the existing hub-page display and query concepts without depending on
  the source repository or `workspace/runtime`.
- Bind only to loopback, choose a conflict-safe port, validate the Host header,
  use local assets, and expose read-only endpoints.
- Use a simple one-way live update channel such as server-sent events.
- Stop the server with the foreground command; consider a per-user service only
  after the on-demand path is measured and proven useful.

## Acceptance criteria

- The command opens a read-only local dashboard without network egress or
  external page assets.
- It reads each adapter store through the neutral CLI without creating a
  runtime dependency between adapters.
- Live updates appear without reloading the page.
- Port conflicts, stale databases, malformed rows, and command termination are
  handled with clear errors and no orphaned process.
- The dashboard never renders secrets, prompts, code, paths, or feedback body
  content unless a separate explicit safe-view contract is approved.

## Sources

- `tools/build_hub_page.py`
- `docs/installer-strategy.md`
- [#fb0f169b](fb0f169b-apply-adapter-local-diagnostics.md)
