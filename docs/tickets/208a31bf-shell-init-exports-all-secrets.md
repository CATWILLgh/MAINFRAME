---
id: 208a31bf
title: Shell bootstrap exports every stored secret to all descendant processes
status: open
priority: medium
component: install
discovered: 2026-07-15
discovered-from: []
tags: ["security", "secrets", "environment", "installer", "least-privilege"]
---

# 208a31bf: Shell bootstrap exports every stored secret to all descendant processes

## What was observed

The installer appends a shell-init line that enables automatic export, sources the complete `secrets.env`, and disables automatic export afterward. The line is written to `~/.zshenv` and any existing Bash profile files, so every subsequently launched child inherits every entry.

## Why it is a problem

Credentials intended for one tool become available to unrelated applications, build scripts, package hooks, and subprocess dumps. This increases the exposure radius beyond the repository and command that needs each secret.

## Why it is not a duplicate

- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) moved credentials out of OpenCode JSON; it did not constrain process-level distribution from the shared store.

## What probably needs to be done

- Stop globally sourcing the full secret store from shell startup.
- Resolve credentials at the point of use through the `secret` helper or narrowly named environment variables.
- Provide a migration that removes only the exact managed source line and preserves user shell configuration.

## Acceptance criteria

- A fresh child shell does not inherit unrelated stored credentials by default.
- Hub integrations that need credentials still receive only their named values.
- Install and uninstall tests prove idempotent migration of the managed shell-init line.

## Sources

- `install.sh:622-623` — current `~/.zshenv` target and exact managed source line.
- `install.sh:687-693` — current writes to `~/.zshenv`, existing
  `~/.bashrc`, and existing `~/.profile`.
- `core/resources/credential-tools/secret` — authored helper source.
- `dist/claude-code/scripts/secret` — rendered helper installed through
  `SECRET_HELPER_SOURCE`.
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

## Re-occurrence noted (2026-07-15)

**Noticed during:** Installer public-contract test expansion (`#f125085c`)
**Where:** `install.sh`, `core/skills/secrets-handling/SKILL.md`,
`core/skills/curl-requests/SKILL.md`,
`core/resources/credential-tools/secret`, and the rendered
`dist/claude-code/scripts/secret`
**Additional details:** Removing the startup export only from the installer would leave the shipped skills and helper guidance claiming that the complete store is loaded into every shell. A coherent fix therefore requires regenerating `dist/codex` and `dist/claude-code`. The active Codex skill path is currently a direct symlink to this repository's `dist/codex/skills/secrets-handling`, so regeneration would immediately alter live delivery even without running `install.sh`. Work is deferred while the user has explicitly limited this phase to checks and changes that do not affect delivery.
