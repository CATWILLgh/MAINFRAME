---
id: 18dd9738
title: Installer and CI trust mutable dependencies and an unverified binary download
status: open
priority: medium
component: supply-chain
discovered: 2026-07-15
discovered-from: []
tags: ["security", "supply-chain", "dependencies", "ci", "checksums"]
---

# 18dd9738: Installer and CI trust mutable dependencies and an unverified binary download

## What was observed

The installer resolves mutable latest or unversioned Python and npm packages. It downloads the latest OSV-Scanner executable directly into `~/.local/bin` and makes it executable without verifying a checksum or signature. CI installs `tiktoken` and `pyyaml` without version constraints and references GitHub Actions by mutable version tags rather than immutable commit hashes.

## Why it is a problem

The same repository revision can execute different third-party code over time. A compromised package release, tag, or download path can affect every project because MAINFRAME installs global tooling and configuration.

## Why it is not a duplicate

- [#10854109](10854109-verify-osv-asset-naming.md) verified release asset naming only; it explicitly did not establish binary integrity or version pinning.

## What probably needs to be done

- Define reviewed versions for installed tools and a deliberate update procedure.
- Verify the OSV-Scanner asset with an upstream checksum or signature before replacement.
- Pin GitHub Actions to immutable commit hashes and pin Python validator dependencies with integrity metadata where the chosen installer supports it.
- Keep updates observable and test them before rollout rather than silently following latest releases.

## Acceptance criteria

- Repeating installation from the same repository revision selects the same dependency versions.
- A checksum/signature mismatch prevents OSV-Scanner installation and preserves the previous binary.
- CI action references are immutable and dependency updates are reviewable diffs.

## Sources

- `install.sh:501-616`
- `.github/workflows/ci.yml:12-16`, `.github/workflows/ci.yml:54-55`
- [GitHub Actions secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)

## Re-occurrence noted (2026-07-15)

**Noticed during:** Claude plugin manifest validation repair (`#09b19ada`)
**Where:** Proposed Claude Code validation step in `.github/workflows/ci.yml`
**Additional details:** The authoritative plugin validator is distributed through npm. The new check will pin the exact Claude Code version and keep render-drift tests independent of npm, but CI will still trust registry availability and package integrity until this supply-chain ticket defines the repository-wide lock and verification policy.
