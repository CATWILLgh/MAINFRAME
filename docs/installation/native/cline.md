# Cline Desktop — native orientation

Inspected 2026-11-01 against installed **Cline Desktop 0.0.46** (`bot.cline.app`,
`/Applications/Cline.app`). Its `code-sidecar` embeds SDK core **0.0.93**.
This is Desktop evidence. The maintained legacy CLI route remains available,
but no current CLI compatibility, discovery or behavioral acceptance is claimed.
Public Desktop releases can advance independently of this installed target.

Official references consulted: [configuration](https://docs.cline.bot/getting-started/config),
[plugins](https://docs.cline.bot/customization/plugins),
[subagents](https://docs.cline.bot/features/subagents), and
[SDK plugins](https://docs.cline.bot/sdk/plugins).
The installed Desktop source resolves details that public cross-product documentation
cannot establish for this release.

## Exact shipped evidence

The arm64/x86_64 universal `Contents/MacOS/code-sidecar` contains a NUL-delimited,
readable JavaScript bundle. Read its embedded text without executing the binary;
identify source modules through their retained `sdk/packages/.../src/` comments.
No agent, hub, model session, application service, database or history is needed.

| Shipped artifact | SHA-256 |
| --- | --- |
| `Contents/MacOS/code-sidecar` | `d508c4d9cc7740ee23b3f5c1cb6fa7915bb1c6752a5d09105750ef1222fff276` |
| `Contents/Resources/bin/extensions/plugin-sandbox-bootstrap.js` | `c3d22e3207ae0c8b991945606943855757c949764ba4048def54822990c01524` |

Relevant current functions and their observed semantics:

- `resolvePluginConfigSearchPaths` includes `~/.cline/plugins`;
  `discoverPluginModulePaths` recursively discovers `.js`/`.ts` modules, or
  declared `package.json` entries. A plain module requires no internal database
  registration or package installation.
- Desktop `resolveDesktopPluginBootstrap` and `configurePluginBootstrap` select
  the shipped bootstrap above. `resolveAndLoadAgentPlugins` loads discovered
  modules through the native registry. Default runtime config extensions include
  `plugins` and `hooks`; disabled plugin settings remain effective.
- The native bootstrap's `initialize` accepts the generated module, validates
  its `hooks` manifest, and reports `beforeTool` with no failures. An isolated
  worker probe through that actual shipped bootstrap returned recoverable
  `{skip: true, reason: ...}` and informational `{appendContext: ...}` from
  synthetic inputs. This proves module loading and control serialization, not
  activation in the user's running conversation.
- `AgentRuntime.prepareToolExecution` maps `skip` to an error tool result and
  continues the run; `findCompletingToolMessage` requires a successful completion
  tool result. `stop` throws instead. `callAfterRunHooks` ignores return values.
- `session-factory` merges the built-in file-hook extension before discovered
  plugins; `mergeAgentExtensions` preserves first-seen order. File guards
  therefore remain installed: changing them to capture-only would remove
  protection when the plugin is disabled or fails to load. The plugin only adds
  a completion-tool check, with no duplicate shell guard or edit advice.
- Native plugin hooks default to 3000 ms. The thin bridge kills its Python child
  after 2300 ms and returns no control on failure, malformed output or timeout.
  Longer analyzers remain on the existing synchronous file-hook route.

## Product-private delivery

| Component | Maintained Cline destination |
| --- | --- |
| Global instruction | `~/.cline/rules/mainframe.md`, one managed block |
| 23 skills with all approved resources | `~/.cline/skills/<name>/SKILL.md` and relative resources |
| 7 roles | `~/.cline/agents/<name>.yml` |
| 8 explicit user workflows | `~/.cline/workflows/<name>.md` |
| Tool hooks and unchanged detectors | `~/.cline/hooks/PreToolUse`, `PostToolUse`, transport and `detectors/` |
| Additional native completion binding | `~/.cline/plugins/mainframe.js` |
| Private bounded detector state and ownership receipt | `~/.cline/data/mainframe/` |

Rules, skills, profiles and workflows use current native discovery paths.
Cross-product compatibility roots such as `~/.agents/` are not owned by this
Cline delivery. Existing settings, histories, sessions, authentication, user
plugins and foreign files are preserved. The shared credential helper and
metadata index keep their separately inventoried ownership.

## Profiles and delegated runtime

`parseConfiguredAgentConfig` requires YAML frontmatter `name`, `description`
and a nonempty Markdown prompt. It supports `tools`, `skills`, `providerId`,
`modelId` and `maxIterations`. `loadConfiguredAgentConfigs` reads project and
global `.cline/agents` YAML files. `createConfiguredAgentTools` exposes profiles
as `subagent_<sanitized_name>` tools with a single `prompt` argument; hyphens in
MAINFRAME names become underscores. Generic `spawn_agent` accepts only
`systemPrompt` and `task`.

Every profile binds its required method with native `skills:` metadata.
`DefaultRuntimeBuilder` creates a skill executor restricted to that configured
skill list. Three read-only roles allow `read_files, search_codebase`.
`filterToolsForConfiguredAgent` adds `skills` when a skill list exists and then
filters by exact tool name. A pure extracted-function probe against this shipped
filter retained only `read_files`, `search_codebase`, `skills` and excluded
shell, editors, MCP, scheduling and delegation tools. This does not establish
judgment quality or all host permission behavior.

`buildDelegatedAgentConfig` passes the parent's hooks/extensions into a distinct
`SessionRuntime`, preserving `parentAgentId` and its independent conversation.
Native file-hook `createPayloadBase` assigns `taskId = ctx.conversationId`;
`baseContextFromSnapshot` derives that conversation as
`snapshot.conversationId ?? snapshot.runId ?? snapshot.agentId`. The generated
plugin uses that exact expression. Edit capture and completion therefore share
the same scope, while a child conversation never reads its parent's quality
state. Focused fixtures verify unrelated scopes stay quiet.

## Hook contracts and retained limits

`PreToolUse` is synchronous `tool_call`; `PostToolUse` is synchronous
`tool_result`. Inputs include `taskId`, optional lineage, workspace metadata,
`tool_call`/`tool_result` and legacy stringified parameter fields. Output accepts
`cancel`, `errorMessage`, `contextModification` and `overrideInput`.
`cancel` aborts the run. `contextModification` appends responsible-agent context.
Lifecycle files (`TaskComplete`, task start/resume/cancel/error, prompt submit,
shutdown) are detached and their result is unused.

Native `run_commands` uses command arrays, including structured
`{command,args}` entries; the bridge quotes structured argv before unchanged
detector checks. `apply_patch` carries canonical patch text in `input.input`.
`editor` uses `path`, `old_text`, `new_text`, optional one-based `insert_line`;
replacement must match once, creation requires an absent file, insertion follows
native boundaries and line endings. TODO validation calls the unchanged
`check_patch`, `check_edit` or `check_write` detector on only the addressed rows
and notes. Unsupported/malformed forms stay neutral; guard denial does not edit
the requested file. Structured native failed edit results cannot attribute
unrelated changes as successful edits.

All **50** inventory rows are accounted for: **47 installed**, **3 unsupported
full contracts**, with two useful partial bindings:

- `mainframe-code-quality`: exact-edit advice and bounded before-images remain.
  The plugin additionally revalidates attributed findings before
  `submit_and_exit`, returning recoverable `skip` on a positive finding. This
  cannot cover natural delegated completion: delegated `SessionRuntime` does
  not inherit the root's required-completion-tool policy, and `afterRun` cannot
  continue it. Timeout or analyzer failure stays non-blocking.
- `mainframe-fallow-quality`: exact-scope TS/JS analysis remains informative on
  `PostToolUse`. Universal continuation-capable completion timing is unavailable.
- `mainframe-subagent-selection`: full explicit model-plus-effort selection is
  unavailable. Profile model/provider settings are static; generic and profile
  call schemas have no model/effort pair, and the profile schema has no effort
  field. No strict guard blocks valid native defaults or asks callers to pass
  nonexistent controls. No useful deterministic partial binding is claimed.

Skill reminders and checkpoint advice remain independently disableable,
positive-only per-operation context. Unknown tools, failed reads, malformed
payloads, missing runtimes and unavailable checks stay silent or return the
canonical bounded unavailable-check advisory; none is a positive dangerous
finding.

## Acceptance boundary

The focused installer/transport tests prove update convergence, owned-file
migration, modes, disable controls, foreign-file preservation, exact-edit scope,
TODO checks, failed-edit neutrality, completion revalidation and scope isolation.
The shipped bootstrap worker proves module parsing/loading and serialized control.
Source inspection plus the extracted filter proves the current read-only tool
filter. Neither result proves the Desktop UI has activated the delivered files,
a model selected a skill, a workflow was invoked, or a real conversation received
and acted on advice. No model session or current CLI probe is run by installation.

See the [maintained procedure](../cline-installer.md).
