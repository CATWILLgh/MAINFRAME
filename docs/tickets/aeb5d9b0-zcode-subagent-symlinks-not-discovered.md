---
id: aeb5d9b0
title: Make ZCode discover delivered MAINFRAME subagents
status: closed
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

## Resolution (2026-08-06)

**Implementer:** Codex CLI session `019f64b1` (lifecycle + projection), live
acceptance confirmed by the maintainer
**Commits:** `cb49a7d`, `f3f50a1`, `c712df4`, `3a75f7b`, `11446fc`, `958a2c6`
**Summary:** Projected agents are delivered as managed writable regular files
instead of symbolic links, because ZCode's subagent scanner ignores links while
its skill scanner honours them. A managed writable file is updated and removed
automatically only while it is byte-identical to what was written; a locally
edited file is preserved whole, reported as preserved, and omitted from the
executable plan so it cannot block neighbouring managed updates. An existing
v7 managed link migrates directly to a regular file, while foreign or changed
links stay untouched. The maintainer has since used ZCode with these agents in
real work, which is the live acceptance this ticket was waiting for.

**Not satisfied — for the auditor to weigh:** acceptance criterion 6
("diagnostics distinguish file delivered from subagent discovered") is **not
implemented**. `internal/diagnostics/` contains only `plan.go` and has no
discovery, acceptance, or ZCode concept at all. Live discovery is therefore
still established by human observation, consistent with
`adapters/zcode-desktop/capabilities.json:23` recording that no safe native
list command exists. If the auditor treats criterion 6 as blocking, this ticket
should return to `open` for that item alone rather than for the delivery fix.

**Claims to verify on audit:**
- `~/.zcode/agents/` holds seven regular files with mode `0600` and no symbolic
  links; `decision-reviewer.md` matches the maintainer's customized content
  byte for byte.
- A locally edited managed agent is reported as preserved and does not appear in
  the executable plan.
- `go test -count=1 ./...` and `go test -race -count=1 ./...` pass.
- The packaged install → update → rollback → uninstall lifecycle test passes
  except the separately tracked Antigravity 2.5.0 host gate
  ([#9e64c997](9e64c997-antigravity-250-compatibility-gate.md)).
- ZCode skills, instructions, hooks and user-owned configuration are unchanged
  by the agent materialization switch.
