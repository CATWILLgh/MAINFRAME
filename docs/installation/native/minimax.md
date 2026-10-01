# MiniMax Code Desktop

Last checked **2026-09-15** against the locally installed MiniMax Code Desktop
**3.0.71** (`com.minimax.agent`). The installed Plugin V1 and Hook references
still expose the mapping described below. The installer records the observed
release but does not use a hard-coded version allowlist; live recognition and
behavior remain separate evidence.

Use the [maintained installer](../minimax-installer.md). MiniMax's official
Plugin documentation defines Skills at `skills/<name>/SKILL.md` and the
`.minimax-plugin/plugin.json` package root. The installed product's own
`plugin-creator` reference additionally defines local packages under
`~/.minimax/plugins/<plugin-directory>/`, automatic rescanning, and the exact
synchronous Hook V1 contract used here.

## Native mapping

| Canonical category | MiniMax Plugin V1 mapping |
| --- | --- |
| Global instruction | Plugin `SessionStart` and `SubagentStart` additional context; no internal database edit |
| Skills | Plugin `skills/<mainframe-name>/SKILL.md` with every required relative resource |
| Agents | Unsupported: Plugin V1 has no Agent declaration; native Agent CRUD belongs to the `mavis` service |
| Commands | Partial: slash-capable/explicitly invocable Plugin Skills; explicit-only selection cannot be enforced |
| Hooks | One Plugin Hook document and one composite Python transport over root, tool, and Subagent lifecycle events |
| Credentials | Shared `mainframe-secret` helper and repository-local non-secret index |

The global instruction is injected at the real Hook session boundary. Sidebar
switching does not create another `SessionStart`, so it does not repeatedly add
the body during one active session.

## Hook decisions

MiniMax Plugin V1 provides a neutral `PreToolUse` path: the transport emits nothing
when no detector matches, adds `additionalContext` for advice, and emits native
`permissionDecision: deny` only for a positive blocking detector. This preserves
the product's own permission layer on clean calls.

`PostToolUse` receives the original tool input and result. The transport stores
only bounded pre-edit snapshots in private `PLUGIN_DATA`, consumes them after
the matching native tool identity, and never attributes a repository-wide diff
to one edit. Fallow gets a seven-second internal budget inside the native
ten-second handler bound. Its unavailable notice is deduplicated per session.

`Stop` and `SubagentStop` are used only for unresolved blocking findings
introduced by an attributed edit. The bridge honors `stop_hook_active` and also
claims the native session, recipient, turn, and finding identity in private
state. The same stop therefore cannot continue a model forever.

## Package and runtime boundaries

The package contains no symlinks, installer scripts, secrets, native binaries,
or external app references. Its paths and file counts are checked against the
installed V1 limits. The Hook command uses the same Python 3.11+ interpreter
that ran the installer; `apply` refuses to register it if that interpreter is no
longer executable.

Local Plugin recognition is automatic, but source tests cannot establish live
Desktop recognition. After delivery, one fresh conversation is enough to check
the Plugin catalog and supplied Skill context. A full adapter acceptance run is
separate and should exercise one harmless positive and one clean-silence case
per materially distinct event.

Authoritative public references:

- [MiniMax Plugin Marketplace and package format](https://agent.minimax.io/docs/code/agents/plugins)
- [MiniMax Custom Agents](https://agent.minimax.io/docs/code/agents/custom-agents)
- [MiniMax changelog](https://agent.minimax.io/docs/changelog)

## Commit checkpoint advisory

`mainframe-commit-checkpoint` uses PostToolUse (write/edit) to deliver bounded
model context after successful edits. It is independently disableable and never
registers checkpoint advice at Stop or forces continuation. Defaults, metadata
bounds, reset/deduplication, failure behavior and coverage are owned by the
[canonical checkpoint contract](../../../hooks/README.md#adapt-mainframe-commit-checkpoint).
The maintained installer includes its detector and post-edit binding; native
activation remains a separate observation after installation.
