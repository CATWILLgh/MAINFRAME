---
id: 3a22e26d
title: OpenCode and Codex gates depend on the Claude plugin installation path
status: open
priority: medium
component: gate-delivery
discovered: 2026-07-15
discovered-from: []
tags: ["architecture", "opencode", "codex", "claude-code", "coupling", "gates"]
---

# 3a22e26d: OpenCode and Codex gates depend on the Claude plugin installation path

## What was observed

The OpenCode dispatcher and Codex launcher execute shared detectors from `~/.claude/skills/mainframe/hooks/scripts`. Their own adapter installations do not deliver those detector files into an adapter-owned runtime location. Both deliberately degrade to disabled or no-op behavior when the Claude plugin installation is absent.

## Why it is a problem

The adapters are not independently installable even though they are presented as separate targets. A valid `--opencode` or `--codex` installation can silently lack security gates and quality reminders solely because another product's adapter was not installed or its path changed.

## Why it is not a duplicate

[#9a6f7945](9a6f7945-codex-missing-detector-silent.md) covers a missing individual detector. [#6d09e7be](6d09e7be-install-sh-silent-success-on-missing-source.md) covers false installer success. This ticket addresses the architectural cross-adapter runtime dependency that creates the missing detector condition.

## What probably needs to be done

- Give shared gate detectors a neutral, hub-owned runtime location or package a complete detector set with each adapter.
- Make each adapter's generated launcher resolve only its own declared runtime dependency.
- Validate detector availability before publishing the adapter and fail explicit installation if the contract is incomplete.

## Acceptance criteria

- OpenCode gates run after an OpenCode-only installation in an isolated home.
- Codex gates run after a Codex-only installation in an isolated home.
- Removing the Claude Code plugin cannot disable either adapter's gates.
- Tests verify the detector inventory and a real blocking/advisory probe per adapter.

## Sources

- `adapters/codex/gates/mainframe-hook.sh:7-20`
- `adapters/opencode/plugins/mainframe-gates.js:209-223`
- `install.sh:824-834`

## Progress (2026-08-04)

The Codex half of this ticket is complete for the upcoming live window. Its
bundle carries Codex-owned detectors and rules, the launcher resolves only
`${CODEX_HOME:-$HOME/.codex}`, and Codex-only temporary-home installation plus
uninstall coverage proves the Claude plugin root is not required. The ticket
remains open for the independent OpenCode acceptance criteria.
