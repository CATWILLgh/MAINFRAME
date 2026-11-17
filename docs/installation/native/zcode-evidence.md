# ZCode bundled runtime hook evidence

## Desktop 3.18.2.10443 hook contract

On 2026-11-17 the installed `dev.zcode.app` plist reported version `3.18.2`,
build `3.18.2.10443`. Inspection used clone copies of the plist, resource seal,
Node runtime and Electron archive in a private scratch directory. The resources
matched their `CodeResources` SHA-256 entries:

| Resource | SHA-256 |
| --- | --- |
| `Contents/Resources/glm/zcode.cjs` | `08726b5ef69e1e9072828baa4656713cb3aac93bb096938681278c5600312b2c` |
| `Contents/Resources/app.asar` | `236db1e6aeceb5fbbde3e28e69a3fcac4772c11787120efb41548e8d87c5ecb6` |

Strict deep `codesign` verification failed with an invalid-signature message for
arm64. These hashes identify the inspected local resources; whole-app signature
verification did not pass.

The [pinned probe](../../../tests/probes/zcode_current_contract.cjs) dispatches
this build to its [reviewed function slices](../../../tests/probes/zcode_3182_contract.cjs).
It rejects mismatched bytes before extraction. The Node VM runs audited pure
functions and native scanner/parser classes against synthetic in-memory files,
inert hook callbacks and path operations. It imports no application initializer
and starts no app-server, CLI agent, model, auth flow or user-state reader.

```sh
node tests/probes/zcode_current_contract.cjs /Applications/ZCode.app/Contents/Resources/glm/zcode.cjs 3.18.2.10443
```

The probe establishes the following current contracts:

- User `~/.zcode/AGENTS.md` and workspace `AGENTS.md` both load. Default skill
  roots retain user/project `.zcode/skills` and `.agents/skills`; native skill
  and command scanners load the exact body, metadata and disabled-path choice.
  User commands remain under `.zcode/commands`, with filename identity and
  `description`/`argument-hint` metadata.
- User roles retain `model`, `thoughtLevel`, `color`, `injectAgentsMd` and
  `disallowedTools` parsing. Native filtering excludes Edit/Write while keeping
  the Skill tool. This verifies the installed role boundary, not a universal
  read-only shell sandbox or availability of a particular provider model.
- The event enum remains SessionStart, UserPromptSubmit, PreToolUse,
  PermissionRequest, PostToolUse, PostToolUseFailure and Stop. Pre-tool denial,
  post/failure context, `Write|Edit` matching and ApplyPatch matcher aliases
  retain their reviewed semantics. Global configuration disable and individual
  `enabled: false` callbacks are filtered before callback creation.
- Bash and process-hook callbacks use the primary execution port and pre-tool
  cwd. Successful foreground Bash captures cwd; native policy keeps a directory
  inside the workspace and resets an outside directory to its root. SessionStart
  supplies initialized cwd on startup/resume/fork; compact can dispatch again.
  MAINFRAME keeps root capture through compact by excluding that matcher.
- Write responses include exact content and `originalFile`. Edit responses use
  actual old/new strings, `replaceAll` and `originalFile`, including absent/blank
  file creation. PostToolUse receives the raw result; its additional context
  reaches the model attachment path used for immediate Fallow advice.
- Advisory-only Stop output still causes no continuation. Positive Stop feedback
  with context can continue below the native cap of three. Ordinary Agent/Task
  child construction still omits hook runners and workspace-hook ports; the
  call schema still has no per-call model or reasoning-effort field.

Selected anchors below are **UTF-8 byte offsets** in the pinned runtime:

| Boundary | Anchor | Offset |
| --- | --- | ---: |
| Event enum | `Ec={SessionStart:` | 1464507 |
| Compatible stdin | `LPn` | 5146235 |
| Hook output / matcher | `zPn` / `HRo` | 5150549 / 5152269 |
| Configured registrations | `xwt` | 5164486 |
| Pre-tool dispatch | `akt` | 5288845 |
| Tool executor / post-result route | `bMa` | 7346172 |
| Bash request / policy / execution | `w8a` / `_4o` / `W6o` | 7628553 / 7545454 / 7623849 |
| User instruction lookup | `B3s` | 2299664 |
| Skill roots / reader | `Bbo` / `RCn` | 4374393 / 4380151 |
| Command roots / reader | `Kbo` / `MCn` | 4383817 / 4388271 |
| Role parser / user-role loader | `yie` / `rCi` | 1087927 / 14757204 |
| SessionStart / Stop predicate | `Rti` / `jti` | 13527364 / 13529668 |
| Ordinary child constructor | `let qe=new _D(n.sessionId,` | 13463702 |

Static inspection of sealed `app.asar` also traces the default Desktop resolver
`Na` through the Electron Node route `$p`/`Ks` to the packaged `glm/zcode.cjs`.
Its inspected host module `out/host/chunk-O6MP7ZHZ.js` hashes to
`b0213d10b27c1f43370a69af7b358d9f5da3377684fea14a4ebd7bb3ce474aba`;
the runtime definition in `out/host/chunk-IEBWXNOE.js` hashes to
`b20de5221bc64f2ab37ad2e09cf3b0d7b122e1dbacca2c7986d2860ee508b172`.
The definition retains `nativeConfigDir: ".zcode/cli"` and `config.json`.

The narrow adapter update adds the reviewed build to existing full/extended
Desktop mappings and preserves older mappings and unsupported guarantees.
Disposable-home checks cover delivery, convergence, role settings, global and
individual hook disables, attributed edits, Fallow advice and bounded Stop
repair. A fresh running Desktop session's discovery, permission prompts, hook
delivery and model behavior remain separate acceptance; no live activation is
claimed by these source and fixture checks.

## Desktop 3.18.0.10300 hook contract

On 2026-11-12 the installed Desktop plist reported `3.18.0.10300`. The shipped
`Resources/glm/zcode.cjs` matches its resource-seal SHA-256
`26785f28ab8fb9f8b0f3821f2bf71d294f4d0b8bf28108785292f86c7e14090d`.
Full signature verification of the inspected app copy failed. This is evidence
from the pinned runtime resource and isolated code slices.

The [pinned source probe](../../../tests/probes/zcode_current_contract.cjs)
checks matcher aliases, pre-tool denial, successful and failed post advice,
fork and compact dispatch, the Stop predicate and three-continuation cap, and
native Write/Edit result shape. It also checks the ordinary Agent constructor
and schema for the absent child hook runner and per-call selection controls.
Run it against the installed resource without launching the app or a model.

```sh
node tests/probes/zcode_current_contract.cjs /Applications/ZCode.app/Contents/Resources/glm/zcode.cjs 3.18.0.10300
```

Resume restores the recorded directory and initializes the runtime before
dispatching resume or fork. Compact dispatch uses the mutable working directory.
The adapter registers root capture on initialization sources and keeps the
earlier capture through compaction. Shell tool and process callbacks use the
same execution port and cwd in the primary local runtime. Native Edit with an
empty `old_string` creates an absent file or fills a blank file. Its successful
response supplies an empty or blank `originalFile` and the actual `newString`.
The todo guard and Fallow fallback exercise these supported inputs in their
adapter fixtures. Live Desktop callback delivery and remote installation remain
pending acceptance. [Official hook contract](https://zcode.z.ai/en/docs/hooks)

## Desktop 3.17.2.9661 private skill reader

On 2026-11-04 the installed Desktop plist identified **3.17.2.9661**. macOS
verified the deep signature and accepted the app as Notarized Developer ID.
The resource seal matched the bundled `Contents/Resources/glm/zcode.cjs`
SHA-256 `d9afd58d694f98a5279bf548cdc7646413c125762e86730605a6071f9e0346d6`.
See the [3.17.2 release notes](https://zcode.z.ai/en/changelog).

The shipped Desktop default agent resolver selects the packaged Node bundle.
The extracted native `NodeSkillAdapter` scanner, Markdown loader, and metadata
reader discovered and loaded the exact `mainframe-openspec` body with no
diagnostics in a synthetic `~/.zcode/skills/` tree and honored a disabled path.
This qualifies the user-level package and metadata for skill-only delivery.
Discovery in a running Desktop session remains unverified on this build.

## Desktop 3.17.2.9661 hook contract probe

On 2026-11-10 the installed plist again identified `dev.zcode.app`, build
`3.17.2.9661`. A strict deep signature verification passed outside the sandbox,
and the runtime still matched the sealed SHA-256 above. The
[source-only probe](../../../tests/probes/zcode_current_contract.cjs) checks the
exact bundle hash for each of the two reviewed builds before extraction. It
rejects unknown builds and mismatched bundle bytes.

The Node VM ran the extracted output parser `wIn`, matcher `ZSo` and Stop
predicate `tVo`. The parser retained the PreToolUse denial and reason and the
PostToolUse advice. The `Write|Edit` matcher accepted Edit. Stop continued with
a blocking reason below the native three-retry cap. Advisory-only output,
`continue: false` with a system message, and a block at the cap did not request
another turn.

Static inspection traced the exact Write and Edit response fields through the
successful caller's raw tool result `kt`, the `$ko` PostToolUse dispatch and
the `_In` stdin projection. The caller also projects post-hook advice into
`hookAdditionalContexts`. The public Agent schema `lat` has no per-call model
or effort field. The default child constructor and its `aTt` client-port
projection omit hooks and hook runners. The native event enum still contains
no SubagentStart or SubagentStop.

These checks cover the listed source contracts. They leave live callback
delivery, command and role discovery, and full installation acceptance open.
The installer permits the selected-skill route on this build.

## Desktop 3.17.1.9553 full delivery

The same pinned bundle below was re-inspected for full Desktop delivery on
2026-11-01. The [source-only probe](../../../tests/probes/zcode_current_contract.cjs)
executes only extracted pure output-parser, matcher and continuation functions
in an isolated Node VM. PreToolUse deny and PostToolUse context pass; advisory
Stop output cannot continue, positive Stop output continues below count three,
and count three cannot continue. `systemMessage` plus `continue: false` supplies
no non-blocking warning channel. The maintained adapter keeps native bounded
repair retries and labels a still-positive retry unresolved. This is source and
fixture evidence, not observed Desktop acceptance.

Native `Write` returns `filePath`, `originalFile`, `content` and `type`; native
`Edit` returns the exact original text, matched old/new strings and `replaceAll`.
The successful tool caller passes the unformatted result `xt` to `Lko` before
model-content projection, and `hIn` includes it as `tool_response`. Post-hook
contexts are merged into `hookAdditionalContexts` for the responsible model.
These fields permit an immediate Fallow partial binding with an in-memory diff:
the bridge uses only the addressed response, verifies its postimage against a
bounded file read, and supplies whole-file ownership only for Write. It retains
no source, patch, diff or broad dirty-worktree snapshot. Missing/conflicting
responses and concurrent postimage changes return bounded unavailable advice.
Native Edit's empty-replacement line-break rule is covered by fixtures.

The public Agent schema `cat` exposes only `description`, `prompt`,
`subagent_type` and `run_in_background`. Neither per-call model nor effort exists;
the strict canonical selection guard cannot be bound to it. The Markdown role
parser `toe` still projects `model` and `thoughtLevel` through `ire`, plus color
and AGENTS.md injection. Those user presets are preserved. They do not establish
explicit choices by the delegating agent. The current default child constructor
and its `sTt` client-port projection omit hooks and hook runners. The native
hook-event enum contains seven events, with no SubagentStart or SubagentStop.
Primary-only scope is consequently retained from current evidence.

The current source retains user `AGENTS.md` lookup in `mPs`, private command
roots in `jpo`/`kSn`, role scanning under `storageRoot/agents` and the `SKILL.md`
entrypoint. The [official hooks](https://zcode.z.ai/en/docs/hooks) and
[subagent definition](https://zcode.z.ai/en/docs/subagents) references corroborate
the user-level configuration and role presets. The hook page still says project
hooks are ignored, while this bundle contains workspace trust machinery; this
route writes only user configuration and does not claim workspace-hook support.

Disposable current-build tests cover all 50 inventory rows, convergence, exact
Fallow scope and deduplication, no source retention, native enable toggles,
global disables and role-setting preservation. Current full delivery includes
the tested Fallow runtime dependency; older build allowances are unchanged.
No CLI agent, app-server, application initializer or model probe was used.

## Desktop 3.17.1.9553 task command and pre-edit guard

Reviewed 2026-11-01 from `/Applications/ZCode.app/Contents/Info.plist` and shipped
`Contents/Resources/glm/zcode.cjs`, SHA-256
`9afd565a104d660259e6bdeeaa5cb8abc74a908559e21aa3c5f6a06f2a9da6c6`.
The command-root functions `jpo`/`kSn` include user `.zcode/commands`; `Wln`
appends unconsumed command text under `User arguments:`. The native tool schemas
retain `Write.file_path/content` and `Edit.file_path/old_string/new_string/replace_all`.
`hIn` emits native snake-case tool aliases, `F_a` projects the PreToolUse deny
and reason, and the main executor rejects `permissionBehavior === "deny"`
before tool execution. An isolated Node VM executed only extracted pure `Wln`,
`gxs`, `bIn`, `vIn` and `F_a` functions: prose argument expansion and the bounded
deny result passed. The default child constructor still omits hook runners;
the mapping retains primary-runtime scope. The [official hooks contract](https://zcode.z.ai/en/docs/hooks)
corroborates user configuration, `Write|Edit` matching, process argv, aliases,
deny output and fresh-session snapshots. Disposable tests in
[test_todo_zcode.py](../../../tests/test_todo_zcode.py) cover the narrow same-source
route, preservation, convergence, conflicts, canonical Write/Edit denial and
disabled or missing cached implementations. No application initializer, CLI,
model, live configuration or acceptance session was used. The narrow `/todo`
route remains available alongside the full route validated above.

## Desktop 3.14.5.7961 skill delivery

Reviewed 2026-10-09 from the installed application plist and shipped
`Contents/Resources/glm/zcode.cjs`, SHA-256
`fad4c35c4c36ec210d8a06d3fa0e77de23c8545e2eb6ff90aea1eb38d1e6275f`.
This matches the bundle identity already recorded below for skill discovery.
Its scanner retains the `SKILL.md` entrypoint and directory exclusions.
The initially validated route permitted only Markdown skill additions/replacements in an
existing same-source receipted Desktop installation. Disposable tests establish
acceptance of a new reference and rejection of role, executable, removal and
fresh-installation changes; existing receipt reconciliation rejects edited
owned files. Hook/role/settings mapping is not newly accepted by this mode.
Native discovery and model use in a fresh conversation remain separate.

### Existing instruction and detector update (2026-10-13)

Current build 3.14.5.7961 still ships the exact SHA-256 above, identical to
3.14.4.7912's reviewed runtime. The bounded reminder-contract probe passes
against this installed bundle. Its context source `bls` resolves the user
`~/.zcode/AGENTS.md` (offset 2096380); the default source list contains AGENTS.md.
The unchanged PreToolUse schema retains permissionDecision and reason, and
existing process registrations/transport remain unchanged. The canonical
stdlib destructive detector update only preserves unquoted shell newline
boundaries; it adds no native event or output contract.

The existing-installation mode now also permits replacement of the receipted
managed global instruction and exact existing destructive detector with
unchanged modes. Disposable tests cover update, convergence, transport rejection
and the existing skill-only restrictions for unrelated components. This is not
fresh-install or full native acceptance for the new app build. The official
hooks page timed out during this pass; shipped source and the previously
recorded identical bundle provide the bounded compatibility evidence.

Reviewed 2026-09-08, ZCode Desktop 3.11.2 (build 3.11.2.6792), macOS.
The inspected artifact was
`/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`, SHA-256:

```text
e9f1868c0fdb863537ed910ee3828b9be96b8c2fd805473f63b439e1113266b8
```

This is source inspection and execution of extracted functions, **not live
Desktop acceptance**. No application initializer, CLI agent, model turn, UI,
service, history, transcript, or credential store was used. The bundle is not
copied into this repository or installed as MAINFRAME payload.

## Live Desktop acceptance

On 2026-09-08, a fresh ZCode Desktop session on the same build exercised the
maintained primary-runtime bindings through native Bash. The actual tool results,
rather than the model's summary, established all five expected outcomes:

- `mainframe-secret-access`, `mainframe-destructive-operations`, and `mainframe-commit-secrets` denied their
  harmless fixture calls with the corresponding bounded MAINFRAME reasons;
- `mainframe-rg-short-replace` allowed the inert command and appended the correction as
  hook context;
- the clean destructive-detector case ran without MAINFRAME context.

The fixture commit was not created, the synthetic matched value was not returned,
and the private fixture was removed after checking its temporary-directory
boundary. The same session exposed all 14 MAINFRAME skill identities and six
role identities, and loaded `mainframe-harness-feedback` through the native Skill
mechanism. Catalog presence remains discovery evidence only for the other skills
and roles; it does not prove their bodies, resources, permissions, or behavior.
The request context also contained the exact canonical global instruction inside
ZCode's native `agentsMd` system reminder, attributed to `~/.zcode/AGENTS.md`.
No command workflow or delegated role behavior was exercised.

On 2026-09-14, two ordinary primary-runtime Desktop sessions on the same build
also exercised the installed `mainframe-code-quality` lifecycle. Across 674 native
`Write` or `Edit` attempts, tool results carried 18 attributed quality findings,
12 growth advisories, and two bounded protection-unavailable notices; the other
edit events added no `mainframe-code-quality` context. One positive Stop block reached the
model, and 29 later normal stops completed without that block repeating. This
establishes live post-edit delivery, positive completion continuation, and
successful release after revalidation. It does not change the unsupported
advisory-only Stop boundary below.

The same inspection exposed 53 noisy `mainframe-commit-secrets` unavailable advisories.
Forty-seven came from parsing each physical line of a quoted multi-line commit
message independently; the rest treated a pipeline elsewhere in the command as
making an earlier literal `cd` conditional. The parser now accumulates quoted
shell fragments across physical lines and evaluates only operators adjacent to
`cd`. Replaying the 53 redacted command structures parsed every actual commit
invocation without an unavailable result, while regression cases retain neutral
handling for `cd` in a pipeline or OR-list. The 101-test canonical hook suite
passes, and the maintained installer delivered the corrected detector.

## Reproduce the bounded check

From the repository root, run the developer-only
[contract probe](../../../tests/probes/zcode_native_contract.cjs):

```sh
node tests/probes/zcode_native_contract.cjs /Applications/ZCode.app/Contents/Resources/glm/zcode.cjs
```

It first verifies the complete bundle hash, then extracts reviewed functions into
a Node VM without application imports, filesystem access, or runtime adapters.
It asserts the actual child constructor arguments and lifecycle callsites as
well as executing the Stop decision functions. It prints the hash, result, and
zero-based UTF-8 byte offsets with one-based line numbers. A changed build fails
before extraction; review its mechanisms before changing the pin. The probe
passed against the artifact above. It is not part of ordinary installation and
does not prove native discovery or callback delivery.

## Source anchors and conclusions

The minified artifact has long lines; offsets identify the relevant mechanism
more precisely. The probe regenerates these anchors.

| Mechanism | Native name | Byte offset; line |
| --- | --- | --- |
| Bash strict input | `gK` | 800063; 71 |
| Bash execution request | `eQo/createExecutionRequest` | 10105662; 2284 |
| Bash cwd policy | `n4r/decideBashCwdPolicy` | 10023882; 2273 |
| Tool Pre/Post payloads | `jCr`, `zCr` | 7832555, 7834211; 2060 |
| Compatible hook stdin | `fft/createClaudeCompatibleHookStdin` | 10464326; 2550 |
| Hook project environment | `hft/createPluginEnvOverlay` | 10465348; 2551 |
| Context initialization | `n$r/ensureContextInitialized` | 10897160; 2674 |
| Startup ordering | `Gqr/executeTurn` callsite | 11051382; 2738 |
| Resume ordering | `y7r/resumeFromStore` callsite | 10951833; 2705 |
| SessionStart dispatch | `T7r/runSessionStartHooks` | 10959396; 2706 |
| Default child construction | `KUr/createDefaultSubagentPort` | 10883897; 2674 |
| Hook runner construction | `R0i/createRuntimeHookRunner` | 11189883; 2741 |
| Hook output processing | `zNr/processHookOutput` | 10468657; 2552 |
| Stop continuation predicate | `R7r/shouldContinueAfterStopHooks` | 10960676; 2706 |
| Normal Stop consumer | conditional injection callsite | 10983036; 2711 |
| Post context projection | `$Er` | 7876596; 2092 |

### Bash cwd and runtime root

Bash has no `cwd` or `workdir` input field: its strict schema accepts command,
timeout, description, background execution, and sandbox override. Its execution
request uses the runtime working directory, also supplied to PreToolUse. Shell
commands may change directories internally. Successful foreground main-runtime
commands capture `pwd -P`; `D3r/executeBashHandler` updates cwd before PostToolUse.
The policy retains a directory inside the workspace or resets it to the root.
Background and subagent executions do not persist cwd changes. This establishes
cwd persistence between subprocesses, not persistence of arbitrary shell state.

Subsequent hook payloads expose no independent `workspaceRoot`.
`CLAUDE_PROJECT_DIR` and `ZCODE_PROJECT_DIR` both use the mutable event cwd.
Using either as an immutable project root would be incorrect.

There is a source-supported alternative for the primary runtime: capture cwd on
SessionStart with source `startup` or `resume`, keyed by native session ID.
Startup calls context initialization first. Resume restores the session
directory, clears context initialization, and initializes context before its
SessionStart. Initialization sets both working directory and workspace root from
the same context snapshot. Consequently a resume capture replaces the prior
capture with the resumed runtime's own root; it does not promise an eternal root
for a session identifier. Later PreToolUse combines that captured root with its
current cwd. Missing capture must remain neutral, without substituting current
cwd or inspecting history.

The pinned `3.11.2.6792` bundle contains only startup and resume SessionStart
callsites. `sessionStartHookRan` becomes true once per runtime, with false
assigned only at class initialization. No clear/compact dispatch was found.
The installed `3.14.3.7762` bundle, SHA-256
`b1df2ef3e5bd76c4af3ecb296bc003a10d3f13191a26610bd0ba940feadad529`,
also contains native `runSessionStartHooks("startup", ...)` and
`runSessionStartHooks("resume", ...)` callsites, but no corresponding clear or
compact callsite. The official protocol lists startup/clear/compact sources, so
the maintained matcher accepts those documented values plus observed resume.
On the current bundle, clear and compact are inert compatibility coverage rather
than a claim that native dispatch was observed.
[Official hooks reference](https://zcode.z.ai/en/docs/hooks)

### Operation identity and primary-runtime scope

Tool Pre/Post payloads carry the same native `sessionId` and `toolCallId`, with
snake_case aliases `session_id` and `tool_use_id`. These form an operation key.
Edit resolves `file_path` relative to its runtime working directory. The Post
input is the final execution input, potentially modified by permission or pre
hooks. Post advice is projected into the model's tool result.

The default subagent constructor passes a distinct child session ID but omits
`hooks`, `hookRunner`, `workspaceHookSnapshot`, `workspaceHookAdmission`, and
`sessionMailboxPort`. Its config projection does not add hooks. With those
omissions, the extracted runner constructor returns `undefined` before accessing
an adapter. Thus native global hook inheritance is absent on this inspected
child path; primary-runtime guards must not be advertised as covering subagents.
The official subagent page describes separate context, but is not evidence of
hook inheritance. [Official subagent reference](https://zcode.z.ai/en/docs/subagents)

### Completion advisory barrier

The extracted output processor and continuation predicate establish:

| Stop output | Result |
| --- | --- |
| Top-level or nested `additionalContext` | Collected but not injected into model history |
| `systemMessage` alone | No additional context and no continuation |
| `continue: true` plus advice | Another model continuation consumes advice |
| `decision: block` plus reason | Another model continuation consumes the reason |
| Either continuation form after three continuations | No further continuation |

The normal completion caller injects Stop context only inside the continuation
branch. There is no independent `systemMessage` delivery in the hook processor.
Positive quality blocking can therefore continue the model, subject to the cap;
nonblocking completion advice cannot retain its canonical timing. Moving it to
PostToolUse or a later event, or forcing a continuation, changes the contract.
The official page likewise describes Stop feedback as a bounded continuation.
[Official Stop contract](https://zcode.z.ai/en/docs/hooks)

The source evidence supports primary-runtime bindings for the four pre-shell
detectors, and the live pass above establishes their native event effects on this
Desktop build. It also supports the native events needed for the retained
`mainframe-code-quality` capture, post-attribution, and positive Stop block, whose
deterministic lifecycle is covered by adapter fixtures. It does not support
complete `mainframe-code-quality` or `mainframe-fallow-quality` bindings with their required
nonblocking completion advice. Keep those delivery limitations explicit.
Cached-callback disable behavior and
the other component-specific behavior boundaries remain separate from this
bounded pass, as described by the [native adaptation guide](zcode.md).


## 3.14.4.7912 reminder revalidation (2026-10-06)

The shipped `Contents/Resources/glm/zcode.cjs` SHA-256 is
`fad4c35c4c36ec210d8a06d3fa0e77de23c8545e2eb6ff90aea1eb38d1e6275f`.
The bounded [source probe](../../../tests/probes/zcode_reminder_contract.cjs)
executes only the reviewed pure output parser in an isolated VM. PreToolUse
and PostToolUse accept additionalContext without a permission decision; the
actual consumer merges both into model content. Native session/tool IDs and
snake-case aliases remain present. The default child constructor still omits
hook runners, so primary-only scope is retained. The old pinned full probe
remains historical evidence; do not repin its renamed functions blindly.

The current [official hooks reference](https://zcode.z.ai/en/docs/hooks)
confirms user configuration, process argv, tool matchers and fresh-session
snapshot semantics. Together with disposable ownership/transport tests, this
supports the maintained full delivery route on this build, without claiming
fresh Desktop acceptance or replaying model probes.
