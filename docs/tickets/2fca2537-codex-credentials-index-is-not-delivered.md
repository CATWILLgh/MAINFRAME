---
id: 2fca2537
title: Codex secrets guidance points to a credentials index the installer never creates
status: open
priority: medium
component: codex-delivery
discovered: 2026-07-15
discovered-from: ["208a31bf"]
tags: ["codex", "secrets", "installer", "delivery", "documentation"]
---

# 2fca2537: Codex secrets guidance points to a credentials index the installer never creates

## What was observed

The Codex projection rewrites the secrets guidance to use `~/.codex/credentials-index.md`, but `bootstrap_secrets` copies the index template only to `${CLAUDE_DIR}/credentials-index.md`. On the current machine the Claude index exists and the Codex index does not.

## Why it is a problem

A Codex agent following its shipped instructions cannot read the promised service and credential directory. This makes named secret discovery depend on a Claude-specific file that the Codex guidance does not mention, and a Codex-only installation cannot establish the documented contract.

## Why it is not a duplicate

- [#208a31bf](208a31bf-shell-init-exports-all-secrets.md) limits process-level secret distribution; it does not own delivery of the non-secret credential index.
- [#3a22e26d](3a22e26d-opencode-and-codex-gates-depend-on-claude-plugin-install.md) covers gate runtime dependencies, not the credential index path.

## What probably needs to be done

- Choose one tool-neutral owner for the editable credential index, or explicitly seed the index for every installed adapter.
- Make generated guidance, the template, the helper, and installer agree on that path.
- Preserve an existing user-edited index and avoid creating divergent copies.

## Acceptance criteria

- A Codex-only installation creates or references the exact credential index path named by its shipped skill.
- Claude Code and Codex consume one authoritative user-edited index rather than independent copies.
- Install, repeat install, and uninstall tests preserve user edits and document ownership of the index.

## Sources

- `dist/codex/skills/secrets-handling/SKILL.md:18-23`
- `adapters/codex/build_codex.py:155-317`
- `install.sh:453`
- Local filesystem inspection, 2026-07-15: `~/.claude/credentials-index.md` exists while `~/.codex/credentials-index.md` does not.
