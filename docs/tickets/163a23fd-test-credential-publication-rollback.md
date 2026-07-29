---
id: 163a23fd
title: Test credential publication rollback with injected failures
status: open
priority: low
component: installer
discovered: 2026-07-27
discovered-from: []
tags: ["credentials", "rollback", "testing"]
---

# 163a23fd: Test credential publication rollback with injected failures

## What was observed

The generic executor suite injects journal and publication failures and verifies
rollback. Credential lifecycle integration tests verify private publication,
stale-state rejection, and concurrent-edit preservation, but do not inject a
failure after the credential target has entered its publication sequence.
The reviewed bulk legacy-transfer command now reaches the same credential-only
publication path and has stale-source, stale-catalog, private-mode, and
legacy-source immutability coverage, but it does not close this
failure-injection gap.

## Why it is a problem

The shared executor provides the rollback behavior, so the remaining risk is
low. A credential-specific failure-injection test would still prove that the
exact target and production wiring preserve the previous user document across
partial publication and journal failures.

## Why it is not a duplicate

- [#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md) covers the
  legacy OpenCode writer. This ticket covers the common transactional
  credential-instance path.

## What probably needs to be done

- Extend the credential lifecycle fixture with injectable executor workspace
  or journal failures.
- Exercise failure after staging and after publication.
- Verify exact previous bytes, mode, identity expectations, journal state, and
  subsequent recovery.

## Acceptance criteria

- Credential-specific tests cover at least one publication failure and one
  journal-save failure.
- A failed operation never leaves partial credential metadata visible.
- Recovery either restores the exact previous document or completes the
  already-authorized transaction according to the common executor contract.
- Relevant credential and executor test suites pass locally.

## Sources

- `cmd/mainframe/credential_lifecycle_integration_unix_test.go`
- `internal/executor/executor_test.go`
- `internal/executor/configuration_apply_test.go`
- `internal/application/credential_review_test.go`
