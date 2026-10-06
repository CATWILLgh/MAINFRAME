# Antigravity Desktop 2.0 native mapping

Reviewed 2026-10-06 against the installed macOS application and current official
documentation for **Antigravity 2.0 v2.16.0**. This page owns product evidence;
the executable route is [the maintained installer](../antigravity-installer.md).

## Native destinations

| Inventory category | Desktop global destination |
| --- | --- |
| Global instruction | `~/.gemini/GEMINI.md` |
| Skills and resources | `~/.gemini/config/skills/<name>/SKILL.md` |
| Custom agents | `~/.gemini/config/agents/<name>.md` |
| Hooks | One owned composite binding in `~/.gemini/config/hooks.json`; foreign entries are preserved |
| Credentials | Compatible global `mainframe-secret` helper plus the canonical non-secret index |

The installed application reports bundle identifier `com.google.antigravity`
and release `2.16.0`. Its Desktop transcripts live below
`~/.gemini/antigravity`; CLI uses `~/.gemini/antigravity-cli`. The maintained
entrypoint accepts only the Desktop surface, so the shared customization root
does not authorize a CLI or IDE installation run.

Official references: [rules](https://antigravity.google/docs/rules-workflows/),
[skills](https://antigravity.google/docs/skills/),
[subagents](https://antigravity.google/docs/subagents/), and
[hooks](https://antigravity.google/docs/hooks/).

## Represented components

The global rule file has a documented 24,000-byte per-file limit. The installer
merges one owned block, preserves outside content, and rejects an oversized
result instead of truncating it. Complete skill packages are copied to the
documented global root with resources and resolved local placeholders.

Custom agents use only documented frontmatter. They are subagent-only, use
sandbox command policy, name one installed skill, and list exact current tool
identifiers. Independent research, test audit, and consequential review use the
documented `pro` tier; implementation roles inherit the caller because their
bounded scope alone does not establish one always-sufficient lower tier.
Read-only roles omit file-edit tools. Implementation roles also omit
`list_permissions` and `ask_permission`: a native A106 attempt rejected the
generated role because `list_permissions` was not registered in that execution
surface, matching the documentation's warning that an unmapped tool name can
break custom-agent execution.

Antigravity skills support both slash invocation and autonomous selection.
The current documentation provides no explicit-only switch. The seven canonical MAINFRAME
commands therefore remain `unsupported` as complete contracts. The installer
retains their useful slash behavior as ordinary skill packages whose discovery
description and body both require the exact `/command` invocation. This is a
prompt-level guard rather than native enforcement, and the state reports that
limitation instead of claiming full equivalence.

## Hook capability boundary

The native schema supports `PreToolUse`, `PostToolUse`, `PreInvocation`,
`PostInvocation`, and `Stop`. For `PreToolUse`, the current contract requires a
decision and offers no neutral/defer value. `allow` authorizes the tool,
`deny` blocks it, and `ask` or `force_ask` forces permission handling. A
conditional MAINFRAME guard cannot return silence on a clean command while
leaving the user's existing native permission decision unchanged.

| MAINFRAME hook | Installed native route | Missing full-contract guarantee |
| --- | --- | --- |
| `mainframe-secret-access` | Positive completed-command match becomes a `PostInvocation` ephemeral remediation message | Automatic pre-tool denial |
| `mainframe-destructive-operations` | Positive completed-command match becomes immediate recovery context | Deterministic pre-tool denial |
| `mainframe-commit-secrets` | A just-recorded HEAD is checked and a redacted positive finding is injected | Prospective staged-content denial |
| `mainframe-rg-short-replace` | Canonical detector advice is injected before the next model decision | Pre-tool timing |
| `mainframe-code-quality` | Exact inserted-text findings are injected after supported edits and revalidated at `Stop` | Pre-edit external diagnostics, growth attribution, and unsupported edit-tool shapes |
| `mainframe-fallow-quality` | Exact supported TS/JS edit diffs are analyzed and injected at `PostInvocation` | Completion-event timing and unsupported edit-tool shapes |

The six preventive/quality contracts above remain `unsupported` in schema-2 delivery;
the separate post-edit checkpoint advisory is fully mapped.
That status describes the missing event guarantee; it does not erase the retained
instruction and skill behavior reported under `retained_partial_bindings`.

The earlier adapter incorrectly returned `{}` as a clean `PreToolUse` result.
A real A106 Desktop task then lost every shell and edit result while reads kept
working. The maintained update removes those registrations rather than changing
them to `allow` and bypassing native permissions. It uses `PostInvocation` for
informational delivery and reserves `Stop` continuation for a revalidated positive
finding. The documented `executionNum` bounds a stable finding to one automatic
continuation in that execution; a later execution can recheck it, and repair
releases it. Project-owned hooks remain
untouched and can still choose a complete native decision when the project owns
that policy.

## Evidence boundary

Disposable tests cover rendering, ownership, convergence, foreign hook
preservation, instruction limits, removal of the unsafe earlier registrations,
post-event deduplication, code-finding revalidation, and Desktop/CLI separation.
They do not prove that a fresh Desktop conversation
discovered or executed skills and agents. That native check belongs to separately
requested acceptance and must not be replaced by launching Antigravity CLI.

## Commit checkpoint advisory

`mainframe-commit-checkpoint` uses PostInvocation (attributable supported edit fragments) to deliver bounded
model context after successful edits. It is independently disableable and never
registers checkpoint advice at Stop or forces continuation. Defaults, metadata
bounds, reset/deduplication, failure behavior and coverage are owned by the
[canonical checkpoint contract](../../../hooks/README.md#adapt-mainframe-commit-checkpoint).
The maintained installer includes its detector and post-edit binding; native
activation remains a separate observation after installation.


## Reminder update

On 2026-10-06, current [rules documentation](https://antigravity.google/docs/rules)
replaced the earlier 12,000-character assumption with a 24,000-byte per-file
limit after includes and a separate aggregate rules budget. The adapter checks
UTF-8 bytes and preserves outside user instructions. Current
[hooks documentation](https://antigravity.google/docs/hooks) retains the
PostInvocation `injectSteps`/`ephemeralMessage` channel and no neutral
PreToolUse decision; `deny_unless_prior_grant` is another gating decision.
Reminder advice therefore joins the existing composite PostInvocation handler,
without a new permission gate or forced continuation. Supported timing and
unavailable role-start advice are in the
[native binding table](../../../hooks/skill-reminder-routing.md#native-bindings).
