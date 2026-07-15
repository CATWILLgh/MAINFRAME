---
id: b4c314d2
title: Honor XDG_CONFIG_HOME in the OpenCode config writer default
status: open
priority: medium
component: opencode
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "xdg", "configuration", "isolation"]
---

# b4c314d2: Honor XDG_CONFIG_HOME in the OpenCode config writer default

## What was observed

The OpenCode release bundle and host layout resolve the adapter root from `XDG_CONFIG_HOME` with `~/.config` as a fallback. The existing `build_opencode.py` command instead defaults `--config` directly to `~/.config/opencode/opencode.json`, so running it without an explicit path writes a different configuration when `XDG_CONFIG_HOME` is set.

## Why it is a problem

Two supported entry points disagree about which OpenCode configuration is authoritative. A user with a custom XDG root can receive a correct bundle preview while the legacy writer reads or changes an unused file under `~/.config`, making updates appear to disappear and breaking adapter-local state expectations.

## Why it is not a duplicate

[#06cb98c8](06cb98c8-publish-opencode-config-and-ownership-consistently.md) covers atomic publication of configuration and ownership state after the destination is chosen. This ticket covers choosing the correct destination in the first place.

## What probably needs to be done

- Resolve the default OpenCode directory from a non-empty `XDG_CONFIG_HOME`, falling back to `~/.config`.
- Derive the default ownership-state path from the resolved config path.
- Keep explicit `--config` behavior unchanged.
- Add isolated tests with custom, unset, and empty XDG values.

## Acceptance criteria

- With `XDG_CONFIG_HOME=/custom`, the default config is `/custom/opencode/opencode.json`.
- With XDG unset or empty, the default remains `~/.config/opencode/opencode.json`.
- Dry-run and write modes report and use the same resolved path.
- The resolved OpenCode config and ownership destinations never fall back into Claude Code or Codex roots; the existing optional Claude MCP source behavior is unchanged.

## Sources

- `adapters/opencode/build_opencode.py:324`
- `adapters/opencode/build_bundle.py:41`
- `internal/hostlayout/layout.go`
- `tools/test_build_opencode.py`
- `docs/tickets/06cb98c8-publish-opencode-config-and-ownership-consistently.md`
