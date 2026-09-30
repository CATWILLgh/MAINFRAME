# ZCode bundled runtime hook evidence

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
