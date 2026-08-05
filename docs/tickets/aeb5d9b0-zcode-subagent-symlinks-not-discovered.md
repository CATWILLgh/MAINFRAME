---
id: aeb5d9b0
title: Make ZCode discover delivered MAINFRAME subagents
status: open
priority: high
component: zcode-desktop
discovered: 2026-08-05
discovered-from: ["#0e9af5a9"]
tags: ["zcode", "subagents", "symlink", "delivery", "live-acceptance"]
---

# aeb5d9b0: Make ZCode discover delivered MAINFRAME subagents

## What was observed
The live ZCode Desktop 3.6.5 installation contains all seven expected
`~/.zcode/agents/*.md` entries. Each entry is a readable symbolic link to a
regular file in the durable MAINFRAME release cache. The adapter's release
assertions explicitly require this linked layout.

After a complete ZCode restart and a manual refresh of Settings -> Subagents,
the application displayed only the built-in `general-purpose` and `Explore`
profiles. None of the seven MAINFRAME profiles appeared. The same profiles
were also absent from the chat `@` picker.

Official ZCode documentation says that saved user subagents are Markdown files
under `~/.zcode/agents/<name>.md`, are loaded on the next run, appear in the
Subagents settings panel, and can be referenced with `@`. ZCode separately
documents symbolic-link import for skills, but does not document symbolic-link
support for user subagent files. The current evidence therefore proves
filesystem delivery but not native discovery; symbolic-link handling is the
leading hypothesis, not yet the confirmed root cause.

## Why it is a problem
Specialized agents are a required ZCode core capability in
`adapters/zcode-desktop/capabilities.json`. The current installer can report a
successful, durable installation while ZCode silently exposes none of those
agents. That removes MAINFRAME's specialized review, research, frontend,
backend, and operations roles without an installation error, so live adapter
acceptance cannot pass.

## Why it is not a duplicate
- [#0e9af5a9](0e9af5a9-zcode-plugin-delivery-contract.md) tracks whether ZCode
  plugin packaging can eventually replace direct-file delivery. This ticket
  covers the currently shipped direct-file contract failing live discovery.
- [#3f750372](3f750372-reject-symlinked-render-targets.md) concerns unsafe
  symbolic links inside the neutral renderer's generated output. This ticket
  concerns whether ZCode accepts links at its user-agent discovery boundary.

## What probably needs to be done
First run a reversible differential probe with one minimal agent: compare the
current linked file with a byte-identical regular file in `~/.zcode/agents/`,
including a full restart and both Settings and `@` discovery checks. If the
regular file is discovered, introduce an adapter-specific regular-file
materialization policy rather than changing link behavior for every adapter.

The lifecycle change must retain claim-scoped ownership, user-edit detection,
atomic replacement, update, rollback, uninstall, and recovery behavior. If a
regular file is also rejected, capture a profile created by ZCode itself and
compare its supported frontmatter with the generated projection. Re-evaluate
plugin-packaged agents under #0e9af5a9 only after the direct-file format is
understood.

## Acceptance criteria
- A failing test or bounded native probe reproduces the rejected delivery shape
  before the lifecycle or projection fix is applied.
- All seven MAINFRAME subagents appear in Settings -> Subagents after a full
  restart and can be selected through the chat `@` picker.
- A fresh install, update, repeated apply, rollback, recovery, and uninstall
  preserve foreign files and user edits while managing the projected agents.
- ZCode skills, commands, instructions, hooks, and user-owned configuration
  retain their current behavior.
- Diagnostics distinguish "file delivered" from "subagent discovered" and do
  not report live acceptance from filesystem links alone.

## Sources
- `adapters/zcode-desktop/build_bundle.py:76-82`
- `adapters/zcode-desktop/capabilities.json:18-24`
- `tools/release_zcode_assertions.py:139-141`
- Live ZCode Desktop 3.6.5 Settings -> Subagents observation on 2026-08-05
- https://zcode.z.ai/en/docs/subagents
- https://zcode.z.ai/en/docs/skill
