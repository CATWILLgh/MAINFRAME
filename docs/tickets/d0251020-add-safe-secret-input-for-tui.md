---
id: d0251020
title: Add a plaintext-safe secret input path for the installer TUI
status: open
priority: medium
component: installer
discovered: 2026-07-17
discovered-from: []
tags: ["tui", "credentials", "security", "mcp"]
---

# d0251020: Add a plaintext-safe secret input path for the installer TUI

## What was observed

The current credential helper accepts `secret set NAME VALUE`. The secret value
is therefore present in the child process argument vector. The first MCP
onboarding milestone can describe an API-key profile, but deliberately does not
collect or persist the key through this interface.

## Why it is a problem

Process arguments can be exposed through process inspection, diagnostics, or
crash reporting. Passing a Context7 API key this way would violate the installer
strategy requirement that credentials never enter previews, logs, journals, or
other observable command metadata. Keyed MCP onboarding cannot become
executable until a safer channel exists.

## Why it is not a duplicate

- [#7ac048e7](7ac048e7-encode-configuration-permission-contracts.md) defines
  destination file and directory modes; it does not cover secret transport into
  the credential helper.
- [#cd5f584d](cd5f584d-complete-configuration-lifecycle-semantics.md) defines
  adapter-owned MCP publication and removal; it assumes credential material can
  already be stored without exposure.

## What probably needs to be done

- Add a credential-helper operation that reads the value from standard input or
  another non-argument channel while keeping the name as the only public
  argument.
- Add masked terminal input in the TUI and pass the bytes directly to that
  operation without putting them in arguments, environment variables, preview
  structures, logs, or executor journals.
- Preserve the helper's existing validation, locking, file mode, backup, and
  atomic replacement behavior.
- Clear transient byte buffers where practical and make failure messages name
  only the credential identifier, never its value.
- Enable keyed MCP profiles only after each selected adapter proves it consumes
  a plaintext-free reference to the stored secret.

## Acceptance criteria

- Process arguments and environment contain no secret value during storage.
- Terminal input is masked and cancellation leaves the credential store
  unchanged.
- Tests cover empty input, invalid names, newline policy, interrupted writes,
  concurrent storage, and absence of secret bytes from errors and previews.
- Context7 keyed onboarding stores the key once in the neutral credential store
  and publishes only adapter-local references for Claude Code, Codex, and
  OpenCode.
- Antigravity remains unsupported for the keyed profile until a plaintext-free
  reference mechanism is verified.

## Sources

- `core/resources/credential-tools/secret:102-115`
- `docs/installer-strategy.md`
- `internal/mcpcatalog/catalog.json`
- <https://cwe.mitre.org/data/definitions/214.html>
