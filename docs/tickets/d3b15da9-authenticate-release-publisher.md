---
id: d3b15da9
title: Authenticate release publisher before enabling network updates
status: open
priority: medium
component: release
discovered: 2026-07-15
discovered-from: ["#40f67f95"]
tags: ["release", "signature", "supply-chain", "tui"]
---

# d3b15da9: Authenticate release publisher before enabling network updates

## What was observed

The packaged release records SHA-256 digests for every bundle manifest and payload file. This detects accidental or malicious modification after the index was created, but the index itself is not signed and therefore does not prove who published it.

## Why it is a problem

A future updater that downloads an attacker-controlled index and matching payload would accept internally consistent hashes. Impact is medium while release input is an explicit local path selected by the user; it becomes high before network delivery is enabled.

## Why it is not a duplicate

- [#40f67f95](40f67f95-complete-release-manifest-for-tui.md) defines complete release contents and integrity.
- [#7a1c1d1d](7a1c1d1d-add-safe-plan-application.md) covers recoverable local mutation after a release has already been trusted.

This ticket covers publisher authenticity at the delivery boundary.

## What probably needs to be done

- Select a release-signing and key-rotation mechanism supported by the publication channel.
- Verify the signed top-level index before trusting any manifest digest or payload.
- Pin the trust root in the bootstrap path and define an explicit recovery procedure for key rotation or revocation.
- Exercise tampered index, wrong signer, expired/revoked key, and rollback-to-old-release cases.

## Acceptance criteria

- A valid release from the trusted publisher passes without network-specific exceptions in the core loader.
- Modified indexes, unknown signers, and invalid signatures fail before any payload is used or filesystem plan is produced.
- Key rotation and revocation behavior are documented and covered by deterministic tests.
- Network download and update remain unavailable until this gate passes an independent security review.
- Local review and Apply state plainly that hashes verify integrity, not publisher identity.

## Sources

- `tools/release_contract.py`
- `internal/releasecontract/loader.go`
- `tools/build_release.py`
- `docs/tickets/40f67f95-complete-release-manifest-for-tui.md`
