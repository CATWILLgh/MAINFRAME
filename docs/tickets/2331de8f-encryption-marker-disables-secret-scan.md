---
id: 2331de8f
title: Repository encryption markers disable the entire secret commit gate
status: open
priority: high
component: gates
discovered: 2026-07-15
discovered-from: []
tags: ["security", "secrets", "sops", "git-crypt", "fail-open"]
---

# 2331de8f: Repository encryption markers disable the entire secret commit gate

## What was observed

The presence of `.sops.yaml` or `.sops.yml`, or any `git-crypt` substring in `.gitattributes`, marks the whole repository as encrypted. `main()` then exits before scanning any staged content, including unrelated plaintext files.

A direct probe confirmed that adding an otherwise empty `.sops.yaml` changes `_is_encrypted_repo()` to true.

## Why it is a problem

Repository-level encryption tools normally protect selected files, not every path. A marker therefore becomes a one-file bypass for plaintext credentials anywhere else in the commit.

## Why it is not a duplicate

No existing ticket covers the encryption-marker bypass or scope of secret scanning.

## What probably needs to be done

- Determine encryption status per committed path, using the relevant SOPS rules or Git attributes.
- Skip only content proven to be ciphertext; keep scanning all other added lines.
- Treat malformed or ambiguous encryption configuration as scanned, not exempt.

## Acceptance criteria

- A repository with SOPS or git-crypt configuration still blocks a plaintext secret in an unrelated file.
- Proven encrypted payloads do not create noisy high-confidence findings.
- Tests cover empty markers, scoped rules, mixed plaintext/ciphertext commits, and incidental `git-crypt` text.

## Sources

- `core/gates/detectors/secret-commit-gate.py:79-97`, `core/gates/detectors/secret-commit-gate.py:169-177`
- Direct encryption-marker probe, 2026-07-15.
