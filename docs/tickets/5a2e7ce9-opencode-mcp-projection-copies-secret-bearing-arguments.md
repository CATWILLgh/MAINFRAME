---
id: 5a2e7ce9
title: OpenCode MCP projection copies secret-bearing command arguments
status: open
priority: medium
component: opencode-configuration
discovered: 2026-07-15
discovered-from: []
tags: ["security", "opencode", "mcp", "secrets", "projection"]
---

# 5a2e7ce9: OpenCode MCP projection copies secret-bearing command arguments

## What was observed

`project_mcp` treats a Claude MCP entry as safe when it is `stdio` and has no `env` object. It then copies `command` and every `args` value into `opencode.json`. Credentials supplied as command-line arguments therefore bypass the function's stated secret-avoidance rule and are persisted in the live config and rolling backup.

## Why it is a problem

Many command-line tools accept tokens, passwords, headers, or connection strings as arguments. Copying those values creates additional plaintext secret copies and can also expose them through process inspection and diagnostic output. The current safety decision examines storage location, not secret-bearing content.

## Why it is not a duplicate

[#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) removed known literal keys from the user's existing OpenCode config. This ticket covers a generator path that can reintroduce secret values from Claude MCP command arguments.

## What probably needs to be done

- Treat `command` and `args` as untrusted secret-bearing fields, not automatically safe strings.
- Project only explicit environment or file references whose values are not resolved by the generator.
- Skip ambiguous entries with a clear report instead of copying them.
- Ensure diagnostics never print resolved credentials.

## Acceptance criteria

- A fixture with a token-like value in `args` is not copied to output or backup.
- Supported reference-based arguments remain references after projection.
- The summary names the skipped server without printing the sensitive argument.
- Tests cover headers, bearer flags, connection URLs, and benign arguments.

## Sources

- `adapters/opencode/build_opencode.py:196-210`
- `adapters/opencode/build_opencode.py:231-245`
- `core/skills/secrets-handling/SKILL.md`
