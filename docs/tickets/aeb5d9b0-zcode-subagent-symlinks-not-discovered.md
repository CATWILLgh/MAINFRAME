---
id: aeb5d9b0
title: Make ZCode discover delivered MAINFRAME subagents
status: in-progress
priority: high
component: zcode-desktop
discovered: 2026-08-05
discovered-from: ["#0e9af5a9"]
tags: ["zcode", "subagents", "symlink", "delivery", "live-acceptance"]
---

# aeb5d9b0: Make ZCode discover delivered MAINFRAME subagents

## What was observed
Before the differential probe, the live ZCode Desktop 3.6.5 installation
contained all seven expected `~/.zcode/agents/*.md` entries. Each entry was a
readable symbolic link to a regular file in the durable MAINFRAME release
cache. The then-current adapter release assertions explicitly required this
linked layout.

After a complete ZCode restart and a manual refresh of Settings -> Subagents,
the application displayed only the built-in `general-purpose` and `Explore`
profiles. None of the seven MAINFRAME profiles appeared. The same profiles
were also absent from the chat `@` picker.

Official ZCode documentation says that saved user subagents are Markdown files
under `~/.zcode/agents/<name>.md`, are loaded on the next run, appear in the
Subagents settings panel, and can be referenced with `@`. ZCode separately
documents symbolic-link import for skills, but does not document symbolic-link
support for user subagent files. A controlled live differential probe then
replaced only `decision-reviewer.md` with a byte-identical regular file. ZCode
immediately displayed it, saved local model and tool selections after the file
was made user-writable, and the orchestrator successfully executed it. The
symbolic-link delivery is therefore the confirmed cause on Desktop 3.6.5.

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
Introduce an adapter-specific writable-file materialization policy for agent
files without changing link behavior for other adapter artifacts. Treat the
agent as a managed configuration file: update and remove it automatically only
while unchanged, preserve a locally edited file as a whole, and report that
preservation without blocking unrelated managed updates. A foreign file must
remain a blocking conflict instead of being adopted or overwritten.

The lifecycle change must retain claim-scoped ownership, user-edit detection,
atomic replacement, update, rollback, uninstall, and recovery behavior.
Field-aware merging of local preferences with later managed prompt updates is
tracked separately in [#ac703f8b](ac703f8b-merge-zcode-agent-user-overrides.md).
Re-evaluate plugin-packaged agents under #0e9af5a9 only if direct writable
files cannot satisfy the lifecycle contract.

The implemented contract uses bundle schema v8, ownership registry v2, and
transaction journal v5. It retains strict readers for legacy v1 link claims
and recoverable v4 link transactions. The initial v7 managed link can migrate
directly to a regular file; foreign or changed links remain untouched. A
selected, claim-backed writable file that was edited or removed locally is
shown as preserved and omitted from the executable plan, so it cannot block
updates to neighboring managed artifacts. Deselecting the component stops
managing that local file without deleting it.

## Acceptance criteria
- A failing test or bounded native probe reproduces the rejected delivery shape
  before the lifecycle or projection fix is applied.
- All seven MAINFRAME subagents appear in Settings -> Subagents after a full
  restart and the orchestrator can execute a designated MAINFRAME subagent.
- A fresh install, update, repeated apply, rollback, recovery, and uninstall
  preserve foreign files and user edits while managing the projected agents.
- A selected customized agent remains associated with MAINFRAME but does not
  block unrelated updates; deselection relinquishes it without deletion.
- ZCode skills, commands, instructions, hooks, and user-owned configuration
  retain their current behavior.
- Diagnostics distinguish "file delivered" from "subagent discovered" and do
  not report live acceptance from filesystem links alone.

## Sources
- `adapters/zcode-desktop/build_bundle.py:86-92`
- `adapters/zcode-desktop/capabilities.json:18-24`
- `tools/release_zcode_assertions.py:150-156`
- Live ZCode Desktop 3.6.5 Settings -> Subagents observation on 2026-08-05
- https://zcode.z.ai/en/docs/subagents
- https://zcode.z.ai/en/docs/skill

## Re-occurrence noted (2026-08-05)

**Noticed during:** Live ZCode Desktop adapter acceptance
**Where:** ZCode Desktop 3.6.5 Settings -> Subagents and orchestrator execution
**Additional details:** A regular writable `decision-reviewer.md` appeared and
executed successfully; the six remaining symbolic links stayed undiscovered.
The chat `@` picker did not expose the agent, so it is not used as the native
execution acceptance contract for this host version.
