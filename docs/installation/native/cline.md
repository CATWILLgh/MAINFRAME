# Cline (Desktop and CLI) — native orientation

Observed 2026-09-22 against **Cline Desktop 0.0.33** (`bot.cline.app`,
`/Applications/Cline.app`) and **Cline CLI 3.0.62** (`@cline/cli-darwin-arm64`,
installed through Homebrew). Both surfaces read the same global root, so one
global installation serves both; desktop and CLI remain separate verification
surfaces under [verification.md](../verification.md#desktop-and-cli).

Evidence sources: current official documentation (`docs.cline.bot`:
`getting-started/config`, `customization/{skills,rules,plugins,hooks}`,
`features/subagents`, `sdk/plugins`), the shipped `@cline/core` and
`@cline/shared` distributions of the installed CLI (type declarations and
bundled runtime), and isolated harmless runtime probes in a temporary directory.
Reread current documentation before relying on any version-sensitive item.

## Global and project configuration roots

`~/.cline/` is the global root and applies to every Cline surface. Project
configuration is `.cline/` at the workspace root. Discovered search paths
(later entries win where the product documents precedence):

| Component | Global | Project | Notes |
| --- | --- | --- | --- |
| Rules | `~/.cline/rules/`, `~/Documents/Cline/Rules`, `~/Cline/Rules`, `~/.agents/AGENTS.md` | `.clinerules/`, `.cline/rules/`, `AGENTS.md` | workspace rules win over global |
| Skills | `~/.cline/skills/<name>/SKILL.md`, `~/.agents/skills/<name>/SKILL.md` | `.cline/skills/`, `.agents/skills/` | `name` must equal the directory name |
| Agents | `~/.cline/agents/*.yml` | `.cline/agents/*.yml` | YAML frontmatter profile plus markdown body |
| Hooks | `~/.cline/hooks/`, `~/Documents/Cline/Hooks` | `.cline/hooks/`, `.clinerules/hooks/` | executable files named after the event |
| Plugins | `~/.cline/plugins/_installed/...` | `.cline/plugins/_installed/...` | managed by `cline plugin install` |
| Workflows | `~/.cline/workflows/`, `~/Documents/Cline/Workflows` | `.cline/workflows/`, `.clinerules/workflows/` | markdown files; optional YAML frontmatter (`name`, `disabled`) |

Provider settings, MCP settings, sessions, teams, and caches live under
`~/.cline/data/`. `CLINE_DIR`, `CLINE_DATA_DIR`, and `--config` / `--data-dir`
relocate these roots; the CLI `--hooks-dir` value defaults to `~/.cline/hooks`.

## Hooks

Hooks are executable files named after the event. File names map to runtime
events as follows:

| Hook file | Runtime event | Phase |
| --- | --- | --- |
| `TaskStart` | `agent_start` | detached, result unused |
| `TaskResume` | `agent_resume` | detached, result unused |
| `TaskCancel` | `agent_abort` | detached, result unused |
| `TaskComplete` | `agent_end` | detached, result unused |
| `TaskError` | `agent_error` | detached, result unused |
| `PreToolUse` | `tool_call` | **synchronous**, result used |
| `PostToolUse` | `tool_result` | **synchronous**, result used |
| `UserPromptSubmit` | `prompt_submit` | detached, result unused |
| `PreCompact` | unmapped | not dispatched |
| `SessionShutdown` | `session_shutdown` | detached, result unused |

Input is one JSON object on standard input with `clineVersion`, `hookName`,
`timestamp`, `taskId`, `sessionContext.rootSessionId`, `workspaceRoots`,
`workspaceInfo` (`rootPath`, `hint`, `associatedRemoteUrls`,
`latestGitCommitHash`, `latestGitBranchName`), `userId`, `agent_id`,
`parent_agent_id`, and a per-event payload object (`preToolUse`, `postToolUse`,
`taskComplete`, `tool_call`, `tool_result`, …). Subagent calls carry their own
`agent_id` with a non-null `parent_agent_id`, so attribution needs no transcript
inspection.

Standard output is a single JSON object or a final `HOOK_CONTROL\t<json>` line,
validated against
`{cancel?, review?, errorMessage?, context?, contextModification?, overrideInput?}`;
context is truncated at 50 000 characters. Result semantics, confirmed in the
shipped runtime:

- `cancel: true` becomes `stop`, and the runtime **throws**, aborting the whole
  run with `errorMessage`/`context` as the recorded reason. It is a hard block,
  not a recoverable per-tool denial.
- `review` is accepted by the schema but has no runtime effect in 3.0.62.
- A recoverable tool denial exists only in the in-process plugin API
  (`beforeTool` returning `skip`), not in the file-hook contract.
- `contextModification` reaches the responsible agent as appended context and
  never blocks.
- Detached lifecycle events cannot inject context, continue the model, or block.
- Hook files must be executable and carry a shebang; otherwise the launch fails
  and the product reports a hook dispatch error.

Probed on a free model in an isolated temporary project: `TaskStart`,
`PreToolUse`, `PostToolUse`, and `TaskComplete` all executed, dispatch ran
through the hub capability layer, and both a `contextModification` advisory and
a `cancel` hard block were delivered. Shell calls arrived as
`run_commands` with `input.commands` as a string array (several commands may
share one call, stringified into `preToolUse.parameters` as
`{"commands": "[\"true\",\"echo hi\"]"}`). Desktop 0.0.33 sends
`apply_patch` as `input: {"input": "*** Begin Patch\\n..."}`; affected paths
therefore come from bounded `Add File`, `Update File`, `Delete File`, and
`Move to` patch headers rather than a separate path field. Built-in tool set of
the same build:
`read_files`, `search_codebase`, `run_commands`, `fetch_web_content`,
`apply_patch`, `editor`, `skills`, `ask_question`, `submit_and_exit`. Tool-event
hooks default to a 120 000 ms timeout.

## Plugins

Documented for SDK, CLI, and Kanban; not documented for the VS Code and JetBrains
extensions. `cline plugin install` copies the package into
`~/.cline/plugins/_installed/<source>/<name>-<hash>` and picks up a top-level
`skills/` directory. In-process plugin hooks use the SDK stages (`beforeTool`,
`afterTool`, `afterRun`, `beforeRun`, `beforeModel`, `afterModel`, `onEvent`) and
can return a recoverable `skip` decision.

Probe result: a freshly installed local hook plugin was **not imported** in a
non-interactive CLI session, in a background (hub) session, or from a project
plugin directory; no load failure appeared in the CLI or hub logs and global
settings had no `disabledPlugins` entry. Plugin loading in this build needs its
own investigation before it can carry MAINFRAME behavior, so the maintained
mapping uses the proven file-hook mechanism.

## Skills, rules, agents, and workflows

- Skills use `SKILL.md` with `name` and `description` frontmatter
  (`description` capped at 1024 characters), load progressively, and surface as
  `/slash-commands`. A skill can also be selected autonomously by description,
  so a skill is never an explicit-only command surface.
- Rules are always-on markdown files with optional `paths:` glob frontmatter for
  conditional activation.
- Agent profiles are YAML-frontmatter files whose body is the system prompt;
  `name` and `description` are required and `tools`, `skills`, `providerId`,
  `modelId`, `maxIterations` are optional. They are exposed as `subagent_<name>`
  when the runtime spawns configured agents; the CLI additionally exposes a
  read-only `use_subagents` research fan-out.
- Workflow files are markdown with optional YAML frontmatter (`name`,
  `disabled`/`enabled`); the body is the instruction text and the name defaults
  to the file name. They are the explicit user-invoked command surface, distinct
  from skills, and appear in the same slash menu. Slash invocation is a
  user-facing action and was not exercised by the non-interactive probes.


Global rules are individual markdown files, each independently toggleable in the
Cline UI, and workspace rules win over global rules. `~/.agents/AGENTS.md` is a
cross-tool compatibility path, not a Cline-owned file; a Cline-only installation
therefore owns exactly one new file under `~/.cline/rules/` and never writes
another product's global instruction system.
