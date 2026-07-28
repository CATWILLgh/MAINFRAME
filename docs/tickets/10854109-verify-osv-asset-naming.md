---
id: 10854109
title: Verify osv-scanner release asset naming against the live GitHub API
status: closed
priority: low
component: install
discovered: 2026-06-03
discovered-from: []
tags: ["install", "osv-scanner", "verification"]
---

# 10854109: Verify osv-scanner release asset naming against the live GitHub API

## What was observed

While fixing the osv-scanner `tag_name` parse bug in `install.sh` (the
`grep '"tag_name"' | sed` greedy regex returned the wrong field → `veyes` →
404), the download URL builds the asset name as `osv-scanner_${os}_${arch}`
(e.g. `osv-scanner_linux_amd64`). The corrected tag parse was verified on
synthetic + the current tag is v2.3.8 — but the **actual asset file names**
for the current release could not be confirmed against the live GitHub API:
the API hit its unauthenticated rate limit (HTTP 403), and the releases HTML
page's JS-rendered asset list failed to load via WebFetch.

## Why it is a problem

If osv-scanner v2 renamed its release assets (e.g. to include a version,
`osv-scanner_2.3.8_linux_amd64`), the download URL would still 404 even with
the now-correct tag. The harm is bounded: the call is best-effort
(`_install_osv_scanner || true`), so a mismatch degrades to a warning, not an
abort — but the `nodejs-deps-audit` hook would stay silent.

## Why it is not a duplicate

Distinct from the `tag_name` parse fix (already shipped). This tracks only the
unverified asset-naming assumption, left unchanged deliberately (not reported
broken, could not be verified live).

## What probably needs to be done

When the GitHub API is reachable (authenticated, or off the rate limit):
`curl -fsSL https://api.github.com/repos/google/osv-scanner/releases/latest | jq -r '.assets[].name'`
and confirm `osv-scanner_<os>_<arch>` (for linux/darwin × amd64/arm64) matches
the real asset names. If renamed, update the `asset=` line in
`_install_osv_scanner` accordingly.

## Acceptance criteria

- Live asset names for the current osv-scanner release confirmed.
- `install.sh` `asset=` construction matches them (or is fixed to).
- A real Linux install downloads osv-scanner successfully end-to-end.

## Sources

- `install.sh` `_install_osv_scanner` (asset name + download URL).
- This session: tag parse fixed + verified; asset naming unverified (rate limit).

## Resolution (2026-07-09)

**Implementer:** autonomous session (Fable 5)
**Commits:** none needed — verification only.
**Summary:** live GitHub API (`releases/latest`, no rate limit this time):
tag `v2.4.0`, assets are exactly `osv-scanner_{darwin,linux}_{amd64,arm64}`
(+ `.exe` variants and checksums) — matching `install.sh:544`'s
`osv-scanner_${os}_${arch}` construction byte-for-byte. No version infix
appeared in v2; the download URL is correct as shipped.
**Claims to verify on audit:**
- `curl -s https://api.github.com/repos/google/osv-scanner/releases/latest`
  asset list matches the pattern above.
