# Layer: Hooks

> Scripts executed by Claude Code on specific events (tool-use, stop, session-start, file-change, etc.). In the hub: `adapters/claude-code/plugin/hooks/scripts/*.py` + registration in `adapters/claude-code/plugin/hooks/hooks.json`, shipped via the `mainframe` plugin.

> Last updated: 2026-06-14 (plugin-migration actualization: scripts + registration live in `adapters/claude-code/plugin/hooks/`, not `adapters/claude-code/export/`). Prior: 2026-06-04 (full event sweep — **exactly 30 events**, ground-truthed against the installed Claude Code v2.1.160 `/hooks` menu). Docs lag the CLI — the running CLI is the authority.

---

## Where it lives / How to install

- In the hub: `adapters/claude-code/plugin/hooks/scripts/*.py` (scripts) + `adapters/claude-code/plugin/hooks/hooks.json` block `hooks.{EventName}` (registration). Hook registration moved here with the plugin migration; `adapters/claude-code/export/settings.json` no longer registers hooks (it still carries permissions / env / other settings).
- On the machine: delivered via the `mainframe` plugin (`adapters/claude-code/plugin/` symlinked as one plugin).
- Activation:
  1. The `mainframe` plugin ships `adapters/claude-code/plugin/hooks/scripts/` + `hooks.json` (loaded when the plugin loads).
  2. Each script is registered under `hooks.<EventName>` inside `adapters/claude-code/plugin/hooks/hooks.json`.
  3. Claude Code's file watcher picks up changes "with brief delay" without a restart.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Full event list — 30 events (ground truth: the installed CLI)

**Authority: the `/hooks` menu of the installed Claude Code**, which enumerates **exactly 30** hook events — the most honest source when published docs and SDK type lists lag it. Descriptions are verbatim from that menu. Matcher + decision-control are cross-checked against `code.claude.com/docs`; **where the docs disagree with the running CLI, the CLI wins** — e.g. `PostToolBatch` / `TeammateIdle` / `TaskCompleted` are real CLI events here, NOT "SDK-only" as the Python-vs-TS SDK literal implied.

| # | Event | Fires when (CLI verbatim) | Matcher | Decision / notes |
|---|---|---|---|---|
| 1 | `PreToolUse` | before tool execution | tool name | allow/deny/ask/defer + `updatedInput` |
| 2 | `PostToolUse` | after tool execution | tool name | block + `updatedToolOutput` |
| 3 | `PostToolUseFailure` | after tool execution fails | tool name | context-only |
| 4 | `PostToolBatch` | after a batch of tool calls resolves | — | — |
| 5 | `PermissionDenied` | **after auto-mode classifier denies a tool call** | — | context — auto-mode-specific |
| 6 | `Notification` | when notifications are sent | type | context-only |
| 7 | `UserPromptSubmit` | when the user submits a prompt | — | block + context; sees prompt |
| 8 | `UserPromptExpansion` | when a user-typed slash command expands into a prompt | `command_name` | block + context; sees expansion metadata and original prompt |
| 9 | `SessionStart` | when a new session is started | source | context (command + mcp_tool only) |
| 10 | `Stop` | right before Claude concludes its response | none | block; `stop_hook_active` guard |
| 11 | `StopFailure` | when the turn ends due to an API error | — | context-only |
| 12 | `SubagentStart` | when a subagent (Agent tool call) is started | agent_type | context; payload `agent_id`/`agent_type` |
| 13 | `SubagentStop` | right before a subagent concludes its response | — | block |
| 14 | `PreCompact` | before conversation compaction | — | block |
| 15 | `PostCompact` | after conversation compaction | — | cannot block |
| 16 | `SessionEnd` | when a session is ending | reason | cannot block |
| 17 | `PermissionRequest` | when a permission dialog is displayed | — | decision hook (allow / deny) |
| 18 | `Setup` | repo setup hooks for init and maintenance | — | context (command + mcp_tool only) |
| 19 | `TeammateIdle` | when a teammate is about to go idle | — | — |
| 20 | `TaskCreated` | when a task is being created | — | — |
| 21 | `TaskCompleted` | when a task is being marked as completed | — | — |
| 22 | `Elicitation` | when an MCP server requests user input | — | command/http/mcp_tool |
| 23 | `ElicitationResult` | after a user responds to an MCP elicitation | — | command/http/mcp_tool |
| 24 | `ConfigChange` | when configuration files change during a session | — | cannot block (async) |
| 25 | `InstructionsLoaded` | when an instruction file (CLAUDE.md or rule) is loaded | — | cannot block (async) |
| 26 | `WorktreeCreate` | create an isolated worktree for VCS-agnostic isolation | — | cannot block (async) |
| 27 | `WorktreeRemove` | remove a previously created worktree | — | cannot block (async) |
| 28 | `CwdChanged` | after the working directory changes | — | cannot block (async) |
| 29 | `FileChanged` | when a watched file changes | — | cannot block (async) |
| 30 | `MessageDisplay` | while assistant message text is displayed | — | — |

**Cadence (docs framing):** per-session (9, 16, 18), per-turn (7, 10, 11), per-tool (1, 2, 3), async (24–29). The rest are situational — subagent (12/13), compaction (14/15), permission (5/17), task (20/21), elicitation (22/23), expansion (8), display (30), batch (4).

**vs the stale 16-event May list:** the running CLI confirms **exactly 30**. Newly surfaced and hub-relevant: `PermissionDenied` (#5 — fires when the auto-mode classifier blocks a tool → a direct, countable signal of **auto-mode friction**, the user's primary workflow), `UserPromptExpansion` (#8 — slash / skill expansion), `MessageDisplay` (#30). The hub currently registers **34 hook commands across 10 of the 30 events** (`SessionStart` 4, `UserPromptExpansion` 1, `UserPromptSubmit` 1, `PreToolUse` 6, `PostToolUse` 8, `Stop` 7, `SubagentStop` 4, plus `PermissionDenied` / `SubagentStart` / `SessionEnd` 1 each) — per `adapters/claude-code/plugin/hooks/hooks.json`, the source of truth. Counts are read from `hooks.json`, not hand-summed.

**Payload + decision-control:** for the telemetry-target events (`PermissionDenied`, `PreToolUse`, `PostToolUse`, `SubagentStart/Stop`, `UserPromptSubmit`, `Stop`, `SessionStart/End`, `PreCompact`) these are documented + verified in **§1.7**. The current Anthropic reference additionally documents `UserPromptExpansion` fields (`expansion_type`, `command_name`, `command_args`, `command_source`, `prompt`); installed Claude Code v2.1.177 contains the event handler, and MAINFRAME unit-tests the consumed contract. Still unverified (names + triggers known, payload schemas not): `PostToolBatch`, `MessageDisplay`, `TaskCreated/Completed`, `TeammateIdle`, `Elicitation*`, `Worktree*`, `CwdChanged`, `InstructionsLoaded`, `FileChanged`, `ConfigChange` — verify before instrumenting them.

### 1.2. Registration syntax

`PostToolUse` (with matcher):
```json
"hooks": {
  "PostToolUse": [{
    "matcher": "Edit|Write|MultiEdit",
    "hooks": [{
      "type": "command",
      "command": "[ -f $HOME/.claude/hooks/scan.py ] && python3 $HOME/.claude/hooks/scan.py || true"
    }]
  }]
}
```

`Stop` (without matcher):
```json
"hooks": {
  "Stop": [{
    "hooks": [{
      "type": "command",
      "command": "[ -f $HOME/.claude/hooks/gate.py ] && python3 $HOME/.claude/hooks/gate.py || true"
    }]
  }]
}
```

Other hook-entry types:
- `prompt`: `{ "type": "prompt", "prompt": "Evaluate: $ARGUMENTS" }` — LLM-based decision.
- `agent`: `{ "type": "agent", "prompt": "...", "timeout": 120 }` — subagent-based.

### 1.3. Stop hook — critical details

> Decision control: return `{"decision":"block","reason":...}` on stdout + exit 0.

> `stop_hook_active` semantics: the payload contains `stop_hook_active: true` if the hook **has already blocked** this same turn. The hook **must** check this and exit 0, otherwise a loop occurs. After **8 consecutive blocks** Claude Code overrides and ends the turn regardless.

### 1.4. Path resolution and cwd

- **Hook `cwd`** = the current directory of the session (may change via `cd`). **Do not use relative paths.**
- **`${CLAUDE_PROJECT_DIR}`** — the directory from which Claude was launched (stable). Source: `code.claude.com/docs/en/hooks` + hub empirics.
- **`${CLAUDE_PLUGIN_ROOT}`** — install root of the plugin a hook ships in, substituted per-element in `command`/`args` so plugin hook paths stay portable across machines — the hub registers every script as `${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<name>.py`. Verified: installed bundle 2.1.177.

### 1.5. File watcher / hot-reload

> "Direct edits to hooks in settings files are normally picked up automatically by the file watcher."

The exact size of the "brief delay" is not documented; empirically it is milliseconds to seconds.

### 1.6. Hooks and subagents (finding 2026-06-01)

Previously it was implicitly assumed that hooks apply only to the main session. Clarified from source:

- **`PreToolUse` / `PostToolUse` / `Stop` fire on subagent tool calls as well**, not only on the main agent. `PreToolUseHookInput` carries the fields `agent_id` and `agent_type` — *"present when the hook fires inside a subagent"* (`code.claude.com/docs/en/agent-sdk/python`). A global hook can therefore distinguish context: empty `agent_id` → main agent, populated → subagent (`agent_type` = agent `name`).
- **Two channels for attaching a hook to a subagent:**
  1. **Global** — `adapters/claude-code/plugin/hooks/hooks.json` (the hub's registration location; Claude Code also accepts global hooks in `~/.claude/settings.json`, which the hub no longer uses for hooks). Fires for all: main agent + every subagent.
  2. **Per-agent** — `hooks:` field in the subagent's frontmatter: scoped to that agent, all events, cleared on completion; `Stop` in frontmatter is runtime-converted to `SubagentStop` (`code.claude.com/docs/en/sub-agents`).
- Plugin-shipped agents ignore per-agent `hooks:` (as well as `permissionMode` and `mcpServers`). MAINFRAME profiles are now user-level agents, so profile-only hooks work in their frontmatter. A hook intended for the main session and multiple agents still belongs in the global `adapters/claude-code/plugin/hooks/hooks.json`. See [agents.md §1.2.1](agents.md).

---

### 1.7. Payload + decision reference — telemetry-target events (verified 2026-06-04)

Closes the "unknown functionality" gap before any telemetry is built. Confirmed against `code.claude.com/docs/en/hooks` — the `PermissionDenied` / `SubagentStart` / `PreToolUse` / common-field shapes are firsthand-quoted from that doc this session; the rest are from the same page (relayed via `claude-code-guide`) and consistent with the SDK `HookSpecificOutput` types — spot-check a specific field before relying on it.

**Common input fields (every event):** `session_id`, `transcript_path` (the conversation `.jsonl`), `cwd`, `hook_event_name`, `permission_mode` (`default` / `plan` / `acceptEdits` / `auto` / `dontAsk` / `bypassPermissions` — availability varies by event). Inside a subagent, `agent_id` + `agent_type` (= the agent's name) are added to tool/subagent events.

| Event | Adds to payload | Honored output | Block? |
|---|---|---|---|
| `PermissionDenied` | `tool_name`, `tool_input`, `tool_use_id`, **`reason`** (auto-mode deny reason) | `{hookSpecificOutput:{hookEventName, retry:bool}}` | no — decision already made; `retry:true` re-offers the call |
| `PreToolUse` | `tool_name`, `tool_input`, `tool_use_id` | `{hookSpecificOutput:{permissionDecision:"allow\|deny\|ask\|defer", permissionDecisionReason, modifiedInput?, additionalContext?}}`; exit 0 = no decision | yes (`deny`) |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response` | `{decision:"block", reason}` / `additionalContext` | yes |
| `SubagentStart` | `agent_id`, `agent_type` | `additionalContext` | no |
| `SubagentStop` | `agent_id`, `agent_type`, `transcript_path` | `{decision:"block", reason}` | yes |
| `UserPromptSubmit` | `prompt` | `{decision:"block", reason}` (erases prompt) / `hookSpecificOutput.additionalContext` (injected alongside the prompt; binary also carries `initialUserMessage`) — verified docs+binary 2026-06-10 | yes |
| `Stop` | `agent_id`/`agent_type`, `stop_hook_active` | `{decision:"block", reason}` | yes |
| `SessionStart` | `source`, `model`, `session_title` | `{hookSpecificOutput:{additionalContext, watchPaths?, reloadSkills?}}` | no |
| `SessionEnd` | end `reason` | — (cleanup only) | no |
| `PreCompact` | (common only) | `{decision:"block", reason}`; **conflict (2026-06-10):** official docs claim `additionalContext` support, the installed binary's schema strings do not show it for this event — unresolved, do not build on it (post-compact `SessionStart(compact)` injection is the verified alternative) | yes |

**Exit-code convention:** on a blockable event, **exit 2** blocks with stderr as the reason; **exit 0** is normal (emit JSON on stdout for a structured decision). A pure **analytics** hook = read stdin → append a record → **exit 0 with no stdout** → invisible to the agent.

**Telemetry privacy boundary:** MAINFRAME records only the denied `tool_name`, never `tool_input` or the free-form denial `reason`. `SubagentStart` and `SubagentStop` carry `agent_type`, which provides lifecycle counts without transcript content. Every row may use `session_id` for per-session aggregation.

---

## 2. Hub usage

### 2.1. Current hub hooks

Live registration: `adapters/claude-code/plugin/hooks/hooks.json` (source of truth). The hub uses **10 of the 30 events**:

| Event | Matcher | Hub scripts |
|---|---|---|
| `SessionStart` | `startup\|resume\|clear\|compact` | `hooklib-smoke-check`, `telemetry`, `init-reminder` (keeps activation on resume, resets its counter after compact, deactivates on startup or `/clear`) |
| `UserPromptExpansion` | `mainframe:init` | `init-reminder` (records the user's direct `/mainframe:init` activation for this primary session; never activates from a payload carrying `agent_id`) |
| `UserPromptSubmit` | `*` | `init-reminder` (after activation, counts only subsequent primary-session user prompts and injects the short re-anchor alongside every 64th prompt; no `Stop` decision or continuation is involved) |
| `PreToolUse` | `Edit\|Write\|MultiEdit` | `length-quality-note` (captures line count and, for Python, AST function lengths before the tool runs; the snapshot remains pending and has no effect unless the matching `PostToolUse` confirms success) |
| `PreToolUse` | `Bash` | `path-validation` (recursive-`rm` circuit breaker: asks for project-root, external, dynamically supplied, shell-expanded, or otherwise unresolved targets; emits no decision for literal targets strictly below the project root, preserving the normal permission flow; never returns `allow`), `secret-commit-gate` (denies `git commit` when its effective content contains a high-confidence vendor token or cannot be established safely; resolves index, `-a`, explicit pathspec/`--only`, `--include`, initial-commit, `git -C`, and literal `cd` forms; scans plaintext files even in SOPS/git-crypt repositories; never stores filenames or matched values in telemetry), `bash-pattern-reminder` (one role-neutral advisory only: detects actual `rg` commands whose short-option cluster contains `r`; ripgrep treats `-r` as replacement text, not recursive search; shell-tokenized to ignore quoted examples and unrelated commands) |
| `PreToolUse` | `Skill` | `telemetry` |
| `PostToolUse` | `Edit\|Write\|MultiEdit` | `scan-suppression-markers` (attributes newly introduced unfinished-code, skipped-test, suppression, and debug-residue markers to `session_id` + `agent_id`; requires task-scoped residue to be replaced by working behavior and its required tests rather than merely deleted; an unrelated annotation is reverted and recorded through the repository ticket workflow without expanding scope; per-edit MultiEdit deltas prevent a removal from masking another addition), `comment-discipline-reminder` (every new comment receives a short review reminder; high-confidence temporary plan/phase/step/discussion references are quoted while their information is still present and attributed to `session_id` + `agent_id`; the writer must preserve durable code rationale rather than delete blindly), `ticket-id-format-reminder` (non-blocking Write-only check: a new ticket uses an unused random 4-hex id, a descriptive kebab-case slug, and a matching frontmatter id; correction renames the file and edits frontmatter without regenerating the body; existing ids remain stable when a slug is clarified), `python-security-scan` (two complete Ruff scans reconstruct the before/after finding delta; only newly introduced findings are stored by `session_id` + `agent_id`, emitted once, and bounded to six rows; pre-existing findings stay silent and each edit revalidates only its current file), `nodejs-security-scan` (one Oxlint scan; emits only findings whose line belongs to the exact Edit, MultiEdit, or Write payload; repeated ambiguous replacements and findings elsewhere stay silent; output is capped at six rows), `fallow-quality-note` (stores only path, line number, and a short digest for still-live TS/JS lines written by this session or subagent; no source text and no model context are emitted at edit time), `length-quality-note` (promotes the matching pending baseline only after a successful file tool call; failed tool calls never own a threshold crossing), `telemetry` (ticket-creation rate + `code_edit` domain bucket with `agent_type` attribution — denominator for profile-agent under-use) |
| `Stop` | `*` | `stop-gate-suppression-markers` (blocks unresolved markers attributed to the main session or any of its subagents; unrelated dirty files and other sessions are excluded), `stop-gate-comment-discipline` (blocks only unresolved temporary-context comment candidates attributed to the main session or its subagents; unrelated dirty files and other sessions are excluded), `python-security-stop-gate`, `fallow-quality-note` (advisory: builds an in-memory unified diff from still-live TS/JS lines attributed to the main session and its subagents, runs `fallow audit --base HEAD --diff-stdin --gate new-only`, reports only conservative `introduced: true` categories, caps output at six rows, then consumes the state so unchanged Stop events neither rerun nor repeat context), `length-quality-note` (advisory: compares the earliest successful baseline from the main session and its subagents with current content; reports only a generic code file crossing 400 lines or a Python function crossing 60, excludes SQL, skips unparseable Python function baselines, caps output at five rows, and consumes state after one comparison; existing oversized code, failed edits, other sessions, and unchanged repeated Stop events stay silent; JS/TS structural growth remains covered by Fallow, while deeper language-specific rules belong to project testing), `memory-reminder` (advisory, non-blocking, main-session-only via absent `agent_id`: emits at most once when the current compact segment first reaches 300k, 600k, or 900k observed input tokens; state is incremental and isolated by `session_id`, compact boundaries restart the sequence, and malformed or undocumented transcript rows fail open without context). On dev installs every `emit_block` reason carries the `harness-feedback` nudge (`_hooklib.FEEDBACK_NUDGE`; silent on plain installs) |
| `SubagentStop` | `*` | `stop-gate-suppression-markers`, `stop-gate-comment-discipline`, `python-security-stop-gate` (each blocks only unresolved findings attributed to that subagent), `telemetry` |
| `PermissionDenied` / `SubagentStart` / `SessionEnd` | `*` | `telemetry` |

Shared scaffolding (`_hooklib.py` + `_markers.py`, stdlib-only) underlies them. Telemetry registrations first pass through `run-telemetry-hook.sh`; outside a Claude `--dev` install it exits before Python, temporary files, or SQLite. Dev installation initializes the adapter-scoped database once in WAL mode, and event writes use `synchronous=NORMAL` with bounded contention retry. `run-hook.sh` buffers the event payload and converts a nonzero internal failure into one role-neutral report per session, event, script, and exit status. On model-bearing events the current model is instructed to relay that exact report to its immediate caller; failures on cleanup-only events are persisted and delivered on the next `SessionStart`. `systemMessage` remains best-effort: Claude Desktop 2.1.222 exposed neither it nor `stopReason` in two bounded UI probes, while `additionalContext` remained available to the model. The other 20 events are unused — see the opportunity map below.

Quality-hook telemetry uses one strict `hook_signal` contract instead of a
different event shape per script. Its outcomes are `noted` for an advisory,
`asked` for a permission decision, `blocked` for a gate, and `resolved` only
after the relevant current state has been revalidated and the attributed
finding is gone. Each row contains only the hook basename, a stable lowercase
rule id, the finding count, and the number of characters emitted into model
context. Session and subagent attribution come from the standard hook payload.
It does not retain source, prompts, paths, finding text, emitted messages,
stdout, stderr, or exception text. The SQLite `hook_effectiveness` view and the
local hub page aggregate signals, sessions, outcomes, and context characters by
hook and rule. These figures measure reach and friction; they do not by
themselves prove that a rule improved product quality.

The aggregate concurrency regression runs every registered handler across 16
simultaneous synthetic sessions. Its context-silent path currently covers 512
parallel invocations and requires zero stdout, zero stderr, and no surviving
launcher temporary files. A separate 32-session probe covered 1,024 invocations
with the same result. Because Claude Code runs every matching handler in
parallel and combines every returned `additionalContext`, overlapping detectors
must suppress a weaker duplicate locally: for example, a TODO receives the
specific unfinished-code instruction, not a second generic comment reminder.
The ticket filename handler is registered only for `Write`, matching its actual
contract instead of spawning on `Edit` and `MultiEdit`.

### 2.2. Opportunity map — unused events (direct purpose + analytics)

Two kinds of opportunity per event: **direct** (the hook acts on the session) and **analytics** (a silent, observe-only hook that logs a fact and returns nothing — `exit 0`, no stdout — for later research). Analytics maps onto the "did the behaviour happen" facts that are otherwise only felt, not counted.

| Event | Direct-purpose candidacy | Analytics candidacy (silent log) |
|---|---|---|
| `PreToolUse` (Task / Agent) | — | **high** — sub-agent dispatch count + `agent_type` |
| `PreToolUse` (advisor) | — | **high** — advisor calls per cycle |
| `PreToolUse` (Skill) | — | high — skill activation frequency |
| `PostToolUse` (Write → `docs/tickets/`) | — | **high** — ticket-creation rate |
| existing detector hooks | (already act) | **implemented** — `log_hook_signal()` records the stable rule, outcome, count, and context-character cost without source data |
| `UserPromptSubmit` | pre-block dangerous commands | high — turns per task |
| `SubagentStart` / `SubagentStop` | global context injection¹ | high — sub-agent lifecycle / count |
| `PreCompact` | — | med — compaction frequency (context-pressure signal) |
| `SessionStart` / `SessionEnd` | (posture already wired) | med — session bound for aggregation |
| `PermissionRequest` | programmatic allow / deny | med — permission-prompt frequency (auto-mode friction) |
| `CwdChanged` / `InstructionsLoaded` / `FileChanged` / `Worktree*` | — | low — situational |

¹ Per-agent hooks now work for MAINFRAME's user-level profiles, but cross-agent context injection still belongs in the global plugin `hooks.json`.

→ The implemented telemetry layer now counts lifecycle behavior and comparable
hook outcomes. The remaining rows are optional future measurements, not a reason
to instrument every event: add one only when it answers a concrete product
question that the current data cannot answer.

### 2.3. Hub principles for hooks

- **Absolute paths** in `"command"`: `$HOME/.claude/hooks/...` or `${CLAUDE_PROJECT_DIR}/...`, not relative.
- **Fail-open, never silent**: an internal hook error exits nonzero to `run-hook.sh`; the launcher itself returns 0 so it cannot turn the failure into a tool denial, but reports the unavailable check once to the immediate caller. Dev telemetry absorbs expected short SQLite contention with bounded retry; a persistent sink failure is reported, while an exhausted busy retry remains a non-blocking telemetry limitation.
- **Self-loop guard** for the `Stop` hook: check `stop_hook_active` and exit 0.
- **Self-exclusion** for marker-detector hooks: `_SELF_FILES` whitelist, otherwise the detector flags itself.
- **Stdlib only** — no venvs or third-party deps, for fast startup.
- **Deterministic hot path** — do not put a remote model call on every edit or
  gate. Claude Code runs all matching handlers in parallel, so a model-backed
  check can multiply latency and subscription usage across simultaneous
  sessions. Evaluate such checks from dev telemetry first; keep safety and
  permission decisions deterministic.

**When observed friction warrants a hook (session signals).** A behaviour is hook-worthy when the transcript shows one of: an explicit correction ("don't… / stop… / never…"), a frustrated reaction ("why did you… / I didn't ask for that"), the user reverting or fixing a change, or the same mistake repeated. Exclude false signals: hypotheticals ("what if I `rm -rf`?"), teaching ("here's what NOT to do"), one-time already-fixed accidents, and pure preferences. Severity sets the response, **within the hub's blocking model** — dangerous / security / data-loss → a `Stop`-gate block (NOT a `PreToolUse` block: those degrade to *defer* in auto-mode and stall the run, so hub blocking lives in the Stop-gates while PreToolUse / PostToolUse stay advisory); style / wrong-target → advisory note; preference → leave it. Adapted from the `hookify` conversation-analyzer; pairs with the `harness-feedback` intake.

---

## 3. Gray zones / open questions

1. ✓ **RESOLVED (2026-06-04).** Full event list ground-truthed from the installed CLI `/hooks` menu (§1.1, exactly 30). Correction: `TeammateIdle`, `TaskCompleted`, `PostToolBatch` are real CLI events (they appear in the menu) — the earlier "SDK-only" read from the Python `HookEvent` literal was a surface-confusion; the running CLI overrides the SDK type list.
2. **Exact size of "brief delay"** for the file watcher — not documented.
3. **Symlink behavior** for `settings.json` with the file watcher — works empirically (the hub relies on it), but without a formal smoke test.
4. **Input payload schema** for the async events (`ConfigChange`, `CwdChanged`, `InstructionsLoaded`, `FileChanged`, `Worktree*`), `Elicitation*`, `Setup`, `PreCompact`/`PostCompact`, `SessionEnd` — the *event names + hook-type support + decision-control* are confirmed (§1.1), but the exact fields each delivers are not laid out in the retrieved docs. Verify the specific fields before building a hook that reads them.
6. **`TaskCreated` (plugin surface) vs `TaskCompleted` (SDK literal)** — adjacent names on different surfaces; confirm which one the CLI actually emits before targeting it.
5. **`Stop` hook behavior after 8 consecutive blocks** — the override happens automatically. What if the hook needs to fire more frequently? No workaround is documented.

---

## Sources

**Authoritative — ground truth:**
- **Installed CLI `/hooks` menu (Claude Code v2.1.160)** — the canonical 30-event enumeration with verbatim descriptions. Beats the docs, which lag.

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/hooks` — cadence model, payload schemas, decision-control, supported hook-types per event.
- `code.claude.com/docs/en/hooks-guide` — patterns, examples, matchers ("specific fields they filter").
- `code.claude.com/docs/en/plugins-reference` — plugin hook events (`TaskCreated`, async events).
- `code.claude.com/docs/en/agent-sdk/python` — `HookEvent` literal + `HookSpecificOutput` union (decision-control per event).
- `code.claude.com/docs/en/agent-sdk/typescript` — TS-only extras (`TeammateIdle`, `TaskCompleted`, `PostToolBatch`).
