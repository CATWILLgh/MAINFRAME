---
id: c71185b2
title: Plaintext API keys in ~/.config/opencode/opencode.json — extract to secrets store
status: open
priority: high
component: opencode-layer
discovered: 2026-07-08
discovered-from: []
tags: ["security", "secrets", "opencode"]
---

# c71185b2: Plaintext API keys in ~/.config/opencode/opencode.json — extract to secrets store

## What was observed
A historical machine-local OpenCode configuration carried provider keys as
literal strings in several remote MCP headers and environment fields. Its
rolling backup created an additional plaintext copy.

## Why it is a problem
Violates the hub `secrets-handling` policy (credential values live only in
`~/.config/credentials/secrets.env`, mode 0600, reached via env substitution).
Plaintext keys in a config file are exposed to any process reading the config,
cloud backups, and accidental pastes. Per OWASP Secrets Management Cheat
Sheet: secrets do not belong in configuration files.

## Why it is not a duplicate
No existing ticket touches OpenCode or these keys; the queue's secrets-related
hits (`cb173a75`, `d245b10d`) concern hub hooks and telemetry, not this file.

## What probably needs to be done
1. Register each value under a descriptive shared credential instance.
2. Replace literals in `opencode.json` with named references. OpenCode supports
   `"{env:VAR}"` substitution; unset var becomes an empty string. Caveat
   (requires verification): substitution inside `mcp.*.headers` /
   `mcp.*.environment` specifically was inferred from the general "any string
   value" doc framing, not a verbatim example — verify on the installed
   version before relying on it.
3. Verify each MCP server still connects (`opencode debug config`, then a live
   session touching context7/web-search).
4. Purge the plaintext from `opencode.json.backup` after rotation (regenerate
   or delete the backup), and consider key rotation since the values sat in
   plaintext.
5. `chmod 600 ~/.config/opencode/opencode.json` while at it.

## Acceptance criteria
- A shape-only secret scan of the live configuration and backups returns no matches.
- All previously working MCP servers connect in a fresh OpenCode session.
- Backup file contains no plaintext keys.

## Resolution (2026-07-08)

**Implementer:** Claude (MAINFRAME session, OpenCode dual-target track)
**Commits:** none (all changes are in machine-local config outside git)
**Summary:** Keys were moved to standalone mode-`0600` files and the five
literals in the live OpenCode configuration were replaced with file
references. File substitution was selected after an empirical desktop probe
showed that shell-provided environment variables were not available there.
The configuration and backup were set to mode `0600`.
The 0600 `opencode.json.backup` intentionally still holds the old plaintext as the
rollback path until the desktop app is confirmed working; it self-rotates on the
first `install.sh --opencode` run. Direct-Bash access to the credentials store was
denied by the hub's own permission layer mid-task (worked as designed); file writes
went through sanctioned paths.

**Claims to verify on audit:**
- A shape-only secret scan of the live configuration returns zero matches.
- The expected number of credential references is present without printing values.
- Credential files and the OpenCode configuration have mode `0600`.
- `opencode debug config` resolves all expected fields without printing values.
- No plaintext shapes under `~/Library/Application Support/ai.opencode.desktop`.
- User-visible: desktop OpenCode, after restart, still reaches all configured MCP servers.
  — CONFIRMED by the user 2026-07-08 after app restart («модели живые»).

## Audit status

The historical machine-local mitigation has not been reverified during the
2026-07-28 repository cleanup because live OpenCode configuration was outside
the task scope. The ticket remains open until the shared credential catalog
owns these references and a value-free audit confirms the current state.

## Sources
- `~/.config/opencode/opencode.json` (live user config)
- https://opencode.ai/docs/config/ — `{env:VAR}` substitution, unset→empty string
- Decision-review of 2026-07-08 (objection 4: backup multiplies secret copies)
- Hub skill: `secrets-handling`
