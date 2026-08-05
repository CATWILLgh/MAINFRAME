# ADR 0090: ZCode Desktop as a local first-class adapter

> Date: 2026-08-05 · Status: accepted for implementation; live activation in progress

## Decision

Add `zcode-desktop` as an independently selectable MAINFRAME component for the
local ZCode Desktop application and its bundled CLI. The first supported host is
ZCode Desktop `3.6.5` (`dev.zcode.app`) with bundled CLI `0.16.1`.

The adapter delivers documented user-level files directly under `~/.zcode`:

- flattened global instructions in `AGENTS.md`;
- public native skills under `skills/`;
- native custom agents under `agents/`;
- restricted method bodies embedded only in their intended agents, with ordinary
  supporting files under `mainframe-agent-methods/`;
- a bounded native hook bridge under `mainframe/gates/`;
- exact managed entries in `cli/config.json` through the release lifecycle.

The component is a closed release bundle. It depends only on `mainframe-cli` and
the shared local credential tools. Selecting it does not require Claude Code,
Codex, OpenCode, Antigravity, MCP, remote workspaces, cloud runs, automations, or
another adapter's files.

## Why direct files are the v1 delivery boundary

Official ZCode documentation describes plugins that can bundle skills, commands,
subagents, MCP servers, and hooks. The installed guide and observed local plugin
runtime did not provide the same confidence for custom plugin-agent execution and
programmatic lifecycle ownership. Direct user roots are documented independently.
Skills and commands passed isolated discovery probes; native agent discovery
required a live Desktop test because the CLI has no safe list command.

MAINFRAME therefore does not write ZCode plugin caches, marketplace state, desktop
databases, Electron IPC state, or `app.asar` internals. Plugin-led delivery remains
an explicit follow-up in ticket `0e9af5a9`.

## Projection contracts

### Instructions and Goal Mode

Shared instruction fragments remain owned by `core/instructions/`; the ZCode
adapter supplies only its preamble and runtime overlay. The result is flattened
because ZCode does not implement MAINFRAME's source import graph.

Native `/goal` is recommended only when the user explicitly asks for a long-running
goal. It manages ZCode continuation and recovery, while `task-workflow` and the
normal MAINFRAME verification gates continue to define engineering completion.

### Skills and restricted methods

ZCode skill metadata is reduced to fields proven by the installed runtime:
`name`, `description`, `when_to_use`, `license`, and `metadata`. Unsupported fields
are not copied.

ZCode has no equivalent of Claude Code's `disable-model-invocation`. A restricted
skill is therefore never placed under `~/.zcode/skills`. Its main method body is
embedded into the intended agent definition. Supporting resources remain ordinary
files outside every skill discovery root. This guarantees discovery isolation, not
filesystem secrecy.

### Agents

Neutral agent contracts are parsed by the shared strict parser. ZCode files contain
only installed-runtime tool names and verified native fields. Unsupported model,
reasoning-effort, turn-budget, and background metadata are not invented; bounded
turn intent is expressed in the agent instructions where useful.

Live Desktop 3.6.5 testing established that ZCode ignores user-agent files delivered
as symbolic links, while it discovers and executes the byte-identical regular file.
Agent files therefore use explicit writable-file materialization; other adapter
artifacts retain their existing link delivery. An unchanged managed agent may be
updated or removed automatically. A locally edited agent is preserved as a whole
configuration file rather than overwritten. Field-aware merging of local model,
color, and tool selections is deferred to ticket `ac703f8b` because safe merging
requires previous-document provenance and an explicit conflict contract.

Writable-file materialization is introduced only by bundle schema v8. The
filesystem ownership registry reads strict legacy v1 link claims and writes v2;
the crash journal recovers valid legacy v4 link transactions and writes v5. An
exact claim-backed v7 agent link can migrate atomically to the v8 regular file.
Foreign, changed, mismatched, and reverse materialization transitions remain
conflicts and are preserved.

The native custom-agent surface is documented as Beta. The release host requirement
pins the bundle identifier and short application version. The observed build is
recorded as qualification evidence, while the local preflight checks the bundled CLI
path and version. Complete apply-time enforcement of the full tuple remains the
explicit compatibility gate in ticket `d0063933`.

### Hooks

ZCode exposes seven native events. The v1 bridge registers the four events that
currently have neutral MAINFRAME detector mappings: `SessionStart`, `PreToolUse`,
`PostToolUse`, and `Stop`. It understands all seven event payload names but does not
claim work for events without a neutral detector.

Each native process hook invokes the internal `mainframe _zcode-hook <Event>`
launcher. The launcher and Python bridge bound execution time and output, preserve
an intentional exit code `2` block, aggregate the strongest detector verdict, and
fail open with a visible diagnostic if the bridge itself is unavailable. Detector
failures are not presented as successful enforcement.

### Shared JSON configuration

`~/.zcode/cli/config.json` is user-owned shared state. MAINFRAME owns neither the
whole file nor the `hooks` object. Bundle schema v7 introduced two claim types,
which remain part of the schema v8 component:

- an exact scalar with captured predecessor state;
- one array entry identified by a selector relative to each entry.

The lifecycle preserves unknown fields and foreign array order. Removal restores a
scalar predecessor and removes only an unchanged owned entry. User drift causes
relinquishment without overwrite. The adapter-local registry records exact managed
values and is removed when its final claim is removed. Invalid, ambiguous, linked,
or concurrently changed state fails closed.

## Local-only product boundary

The core adapter may use the model provider selected by ZCode, but MAINFRAME adds no
cloud service dependency. It does not configure MCP, Context7, remote development,
remote control, bot channels, cloud workspaces, or automations. Those capabilities
remain separate optional product surfaces; see ticket `0f5f833f`.

ZCode-owned memory, checkpoints, browser state, sessions, edit history, and desktop
protocol state remain runtime-owned. MAINFRAME may diagnose their availability but
does not enable, copy, clear, or automate them. See ticket `d93797e1`.

The common `mainframe credentials` catalog and `secret` helper remain available to
terminal calls without copying credential values. `credentials-index.md` is only a
value-free migration fallback. Direct reads of the secret store remain prohibited.

## Release and activation

`dist/zcode-desktop/projection/` contains the generated direct-file projection.
`dist/zcode-desktop/bundle-v2/` contains the closed release component. Generating
the projection cannot delete or replace the bundle.

Repository completion requires deterministic rendering, release validation,
configuration install/update/remove/recovery tests, a temporary-state ZCode probe,
and cross-adapter regressions. It does not authorize changes to live `~/.zcode`.

Live activation is a separate gate: show the exact preview and rollback path, obtain
explicit user approval, apply only MAINFRAME-owned surfaces, restart ZCode, and run
the desktop/CLI acceptance matrix. Instructions, skills, hooks, and one regular-file
agent have passed live checks. Full seven-agent writable delivery and lifecycle
regression verification remain pending, so implementation status is still
`waiting`, not complete.

## Rejected alternatives

1. **Treat the Claude Code plugin as compatible.** Rejected because metadata,
   private-skill visibility, agent execution, and hook configuration differ.
2. **Own all of `cli/config.json`.** Rejected because it would overwrite unrelated
   user configuration and make uninstall unsafe.
3. **Publish restricted methods as hidden-looking skills.** Rejected because ZCode
   does not honor Claude's visibility field.
4. **Enable every native ZCode feature for parity.** Rejected because similar names
   do not establish equivalent authority, lifecycle, or local-only behavior.
5. **Depend on another MAINFRAME adapter at runtime.** Rejected because each release
   component must be independently installable and self-contained.

## Consequences

The adapter covers the local surfaces that can uphold MAINFRAME's contracts without
pretending complete product parity. It also adds a reusable strict JSON-claim
lifecycle for shared configuration. The costs are a pinned desktop compatibility
matrix, one more closed bundle, and explicit follow-up work for native features that
do not yet have a neutral authority or ownership contract.

## Sources

- https://zcode.z.ai/en/docs/agents
- https://zcode.z.ai/en/docs/subagents
- https://zcode.z.ai/en/docs/hooks
- https://zcode.z.ai/en/docs/skill
- https://zcode.z.ai/en/docs/plugin
- `adapters/zcode-desktop/capabilities.json`
- `adapters/zcode-desktop/config_ownership.json`
- `/Applications/ZCode.app/Contents/Resources/glm/packages/zcode-guide-plugin/skills/diagnosing-hooks/SKILL.md`
- `/Applications/ZCode.app/Contents/Resources/glm/packages/zcode-guide-plugin/skills/diagnosing-plugins/SKILL.md`
