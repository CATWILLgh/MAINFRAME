---
id: 6a3cde2d
title: Remove loopback socket dependencies from Tier-1 tests
status: open
priority: low
component: installer
discovered: 2026-07-27
discovered-from: []
tags: ["testing", "sandbox", "mcp", "antigravity"]
---

# 6a3cde2d: Remove loopback socket dependencies from Tier-1 tests

## What was observed

`go test -count=1 ./...` cannot complete in a network-restricted local
environment because `internal/mcpcatalog.TestGitHubStatsReadsCurrentStarsWithTimestamp`
uses `httptest.NewServer`. The test panics when its loopback listener receives
`bind: operation not permitted`. All packages reached before and after that
package pass, and the failure is unrelated to the credential changes that
surfaced it.

The full Python sweep fails for the same environmental reason in
`tools/test_probe_antigravity_mcp_headers.py`: its unit test binds an available
loopback port before exercising the synthetic server.

## Why it is a problem

Tier-1 HTTP-client and protocol contract tests should not require permission to
open a listening socket. The dependencies prevent contributors and autonomous
runs in restricted environments from using the full Go and Python suites as
reliable regression gates.

## Why it is not a duplicate

No existing ticket covers removing loopback listeners from these Tier-1 tests.
The live Antigravity validation ticket [#bce23629](bce23629-live-antigravity-plugin-validation.md)
requires a real host and is separate from making the synthetic protocol test
portable.

## What probably needs to be done

Inject a deterministic `http.RoundTripper` or equivalent request executor into
the GitHub statistics client test. Preserve assertions for the requested URL,
response decoding, current star count, timestamp, and failure behavior without
opening a socket. Split the Antigravity synthetic server's protocol handling
from its listener so the unit test can drive the handler in memory; retain a
separate explicitly local-environment probe for the real socket path.

## Acceptance criteria

- The affected test opens no listener and performs no real network request.
- Its success and failure branches retain their current observable contracts.
- `go test -count=1 ./internal/mcpcatalog` passes in a network-restricted
  environment.
- `python3 tools/test_probe_antigravity_mcp_headers.py` passes without socket
  permission.

## Sources

- `internal/mcpcatalog/github_test.go:13`
- `tools/test_probe_antigravity_mcp_headers.py:61`
- Full local test run on 2026-07-27:
  `httptest: failed to listen on a port: bind: operation not permitted`
