# MiniMax Code Desktop

Last checked **2026-11-01** against installed MiniMax Code Desktop **3.0.73**,
build **3.0.73.170** (`com.minimax.agent`). The public changelog may describe a
newer release; it is not evidence for this installed build. The full maintained
mapping requires release 3.0.73 or newer. File/source checks below do not prove
live discovery, model behavior or compatibility with future releases.

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
| Agents | Seven native file-backed custom Agents at `agents/<name>/agent.md`; read-only tools for the three review/research roles, complete canonical bodies and method links |
| Commands | Partial: slash-capable/explicitly invocable Plugin Skills; explicit-only selection cannot be enforced |
| Hooks | One Plugin Hook document and one composite Python transport over root, tool, and Subagent lifecycle events |
| Credentials | Shared `mainframe-secret` helper and repository-local non-secret index |

The global instruction is injected at the real Hook session boundary. Sidebar
switching does not create another `SessionStart`, so it does not repeatedly add
the body during one active session.

## Current native evidence

Read-only inspection of `Contents/Resources/app.asar` and `app.asar.unpacked`
in the installed bundle established these source paths:

- `@mavis/local-runtime-v2/dist/service/agent/storage/agent-files.js`:
  `listCanonicalCustomAgents` scans direct child directories and admits only
  valid canonical `agent.md` files. `agent.repository.js` merges that roster
  with the host index; `reconcileCanonicalCustomAgents` repairs missing index
  rows at startup. These are supported native file inputs, not installer-owned
  database mutations. The Desktop Agent controller also supports definition-only
  create and import; file delivery avoids authenticated service calls and
  does not create a conversation.
- `agent/storage/canonical-agent-config.js` accepts name, description, model,
  effort, tool allow/deny lists, skill selectors and the Markdown prompt body.
  Model and effort remain absent in the generated files. Edited existing files
  are preserved by ownership conflict rather than silently reset.
- `agent/application/agent-profile.js` carries configuration selectors into the
  execution profile. `turn-system/agent-host/assembly/local-turn-tool-catalog.js`
  applies them to native and MCP tool inventories before exposure. The three
  review/research roles allow only `read`, `glob`, `grep`, `skill`, `web_fetch`,
  `web_search` and `ask_user`; child sessions further remove `ask_user`.
  Arbitrary shell and mutation tools are absent. This is tool filtering, not
  proof of independent reasoning or of every external provider's behavior.
- `service/plugin-system/plugin/package/minimax-reader.js` has Skills, MCP,
  Hooks and host bindings but no Agent declaration. `skill/reader.js` returns
  name, description, content and paths; `plugin/runtime/snapshot-builder.js`
  projects this material without an invocation-policy flag. Neither
  `disable-model-invocation` nor `user-invocable` controls Plugin Skill selection
  in this build. Full explicit-only command parity remains unavailable.
- `@mavis/agent-tools/dist/desktop/builtin-defs.js` defines `write.path/content`,
  `edit.file_path/old_string/new_string/replace_all`, and `task.model/effort`.
  The latter fields are optional natively. The task description asks for user
  choices and forbids inferred choices. Full autonomous preventive selection
  parity is unsupported: the retained pre-creation advisory preserves legal
  defaults and explains that limitation. It never denies omitted selections
  or runs on task continuation tools.
- `@mavis/local-runtime/assets/skills/plugin-creator/references/local-plugin-hooks.md`
  and `@mavis/plugin-hooks/dist/runner.js` preserve the events, exact tool-name
  matchers, stdin context and output effects below.

A disposable, in-process check executed the shipped `AgentFiles` reader against
all seven generated Agent files: all were discovered, parsed without diagnostics,
and resolved their method links. The shipped `filterLocalTurnCapabilityInventory`
retained reads/web search while removing shell, writes, delegation, computer use
and mutating MCP tools for all three restricted roles. The shipped Plugin reader also accepted the generated package (31 Skills and
six Hook handlers). Its real Hook runner accepted session context, task advice
without denial, complete-task clean silence and TODO denial using only disposable
Hook subprocesses. No real session, model, internal database, global user
configuration or authenticated service was used.

## Hook decisions

MiniMax Plugin V1 provides a neutral `PreToolUse` path: the transport emits nothing
when no detector matches, adds `additionalContext` for advice, and emits native
`permissionDecision: deny` only for a positive blocking detector. This preserves
the product's own permission layer on clean calls. The same event validates
addressed TODO `write`/`edit` content and supplies non-blocking task-selection
advice when complete explicit choices are absent. Ambiguous inputs and unknown
tools remain neutral. TODO protection covers these structured edits; shell or external file writes are outside it.

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
installed V1 limits. The local Plugin Hook command uses the same Python 3.11+
interpreter that ran the installer; `apply` refuses to register it if that interpreter is no
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
