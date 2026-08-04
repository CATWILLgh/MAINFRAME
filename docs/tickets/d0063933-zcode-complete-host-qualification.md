---
id: d0063933
title: Enforce the complete ZCode desktop and CLI compatibility tuple
status: open
priority: medium
component: zcode-desktop
discovered: 2026-08-05
discovered-from: []
tags: ["zcode", "compatibility", "host-gate", "cli"]
---

# d0063933: Enforce the complete ZCode desktop and CLI compatibility tuple

## What was observed

The adapter evidence pins bundle identifier `dev.zcode.app`, short application version `3.6.5`, build `3.6.5.4145`, and bundled CLI `0.16.1`. The immutable release host requirement currently enforces only the bundle identifier and short application version. The separate local-surface preflight checks the bundled CLI path and version, but it is not part of the locked apply-time host qualification.

The currently installed host matches the complete tuple. No mismatched build has been observed or activated.

## Why it is a problem

A future ZCode build could keep short version `3.6.5` while changing its build number or bundled CLI behavior. The release selector would admit that unqualified build before the separate preflight reports the mismatch.

## Why it is not a duplicate

The Antigravity compatibility ticket concerns a known installed version mismatch. This ticket concerns the shape of ZCode's host requirement even while the installed host is fully compatible.

## What probably needs to be done

- Extend the typed host requirement with immutable application-build and bundled-executable probes.
- Evaluate those probes during both review and the locked apply refresh.
- Keep the standalone preflight as diagnostics, not as the only enforcement point.
- Reuse the general probe contract for other desktop adapters only where the same semantics apply.

## Acceptance criteria

- A matching short version with a different build is rejected.
- A matching desktop build with a different bundled CLI version is rejected.
- Review and apply evaluate the same complete tuple without executing user-controlled binaries.
- The installed `3.6.5.4145` / `0.16.1` host remains accepted.

## Sources

- `adapters/zcode-desktop/compatibility.py`
- `internal/hostcompatibility/discover.go`
- `tools/check_local_agent_surfaces.py`
- Independent architecture review on 2026-08-05.
