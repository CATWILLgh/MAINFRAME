# Layer: Hooks

> Scripts executed by Claude Code on specific events (tool-use, stop, session-start, file-change, etc.). In the hub: `export/hooks/*.py` + registration in `export/settings.json` `hooks.*`.

> Last updated: 2026-06-04 (full event sweep — **exactly 30 events**, ground-truthed against the installed Claude Code v2.1.160 `/hooks` menu; supersedes the stale 16-event May list). Docs lag the CLI — the running CLI is the authority.

---

## Where it lives / How to install

- In the hub: `export/hooks/*.py` (scripts) + `export/settings.json` block `hooks.{EventName}` (registration).
- On the machine: `~/.claude/hooks/*.py` (symlinks) + `~/.claude/settings.json` (part of the symlink as a whole).
- Activation:
  1. Symlink the `export/hooks/` folder → `~/.claude/hooks/` (via `install.sh`).
  2. Entry in `hooks.<EventName>` inside `export/settings.json`.
  3. Claude Code's file watcher picks up changes "with brief delay" without a restart.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Full event list — 30 events (ground truth: the installed CLI)

**Authority: the `/hooks` menu of the installed Claude Code v2.1.160**, which enumerates **exactly 30** hook events — the most honest source (the published docs and SDK type lists lag it). Descriptions are verbatim from that menu. Matcher + decision-control are cross-checked against `code.claude.com/docs` via Context7; **where the docs disagreed with the running CLI, the CLI wins** — e.g. `PostToolBatch` / `TeammateIdle` / `TaskCompleted` are real CLI events here, NOT "SDK-only" as the Python-vs-TS SDK literal implied.

| # | Event | Fires when (CLI verbatim) | Matcher | Decision / notes |
|---|---|---|---|---|
| 1 | `PreToolUse` | before tool execution | tool name | allow/deny/ask/defer + `updatedInput` |
| 2 | `PostToolUse` | after tool execution | tool name | block + `updatedToolOutput` |
| 3 | `PostToolUseFailure` | after tool execution fails | tool name | context-only |
| 4 | `PostToolBatch` | after a batch of tool calls resolves | — | — |
| 5 | `PermissionDenied` | **after auto-mode classifier denies a tool call** | — | context — auto-mode-specific |
| 6 | `Notification` | when notifications are sent | type | context-only |
| 7 | `UserPromptSubmit` | when the user submits a prompt | — | block + context; sees prompt |
| 8 | `UserPromptExpansion` | when a user-typed slash command expands into a prompt | — | — |
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

**vs the stale 16-event May list:** the running CLI confirms **exactly 30**. Newly surfaced and hub-relevant: `PermissionDenied` (#5 — fires when the auto-mode classifier blocks a tool → a direct, countable signal of **auto-mode friction**, the user's primary workflow), `UserPromptExpansion` (#8 — slash / skill expansion), `MessageDisplay` (#30). The menu header "**16 hooks configured**" equals the hub's own current registrations (§2.1: 2+3+6+5) — an independent confirmation of our count.

**Payload + decision-control:** for the telemetry-target events (`PermissionDenied`, `PreToolUse`, `PostToolUse`, `SubagentStart/Stop`, `UserPromptSubmit`, `Stop`, `SessionStart/End`, `PreCompact`) these are now documented + verified in **§1.7**. Still unverified (names + triggers known, payload schemas not): `PostToolBatch`, `UserPromptExpansion`, `MessageDisplay`, `TaskCreated/Completed`, `TeammateIdle`, `Elicitation*`, `Worktree*`, `CwdChanged`, `InstructionsLoaded`, `FileChanged`, `ConfigChange` — verify before instrumenting them.

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

### 1.5. File watcher / hot-reload

> "Direct edits to hooks in settings files are normally picked up automatically by the file watcher."

The exact size of the "brief delay" is not documented; empirically it is milliseconds to seconds.

### 1.6. Hooks and subagents (finding 2026-06-01)

Previously it was implicitly assumed that hooks apply only to the main session. Clarified from source:

- **`PreToolUse` / `PostToolUse` / `Stop` fire on subagent tool calls as well**, not only on the main agent. `PreToolUseHookInput` carries the fields `agent_id` and `agent_type` — *"present when the hook fires inside a subagent"* (`code.claude.com/docs/en/agent-sdk/python`). A global hook can therefore distinguish context: empty `agent_id` → main agent, populated → subagent (`agent_type` = agent `name`).
- **Two channels for attaching a hook to a subagent:**
  1. **Global** — `plugin-dist/hooks/hooks.json` (or `export/settings.json`). Fires for all: main agent + every subagent.
  2. **Per-agent** — `hooks:` field in the subagent's frontmatter: scoped to that agent, all events, cleared on completion; `Stop` in frontmatter is runtime-converted to `SubagentStop` (`code.claude.com/docs/en/sub-agents`).
- ⚠️ **Critical:** per-agent frontmatter `hooks:` (and also `permissionMode`, `mcpServers`) are **ignored for plugin subagents**. Our agents are plugin agents, so per-agent hooks **do not work** for them. → A **cross-agent hook** (needed by both the main agent and subagents) in the hub can live **only in the global `plugin-dist/hooks/hooks.json`**. See [agents.md §1.2.1](agents.md).

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

**Telemetry implication:** `PermissionDenied` is the prize — `tool_name` + `tool_input` + `reason` let an auto-mode-friction log record *what was denied and why* with zero guessing. `SubagentStart` carries `agent_type` → a clean sub-agent-usage key. Every event carries `session_id` → per-session aggregation for free.

---

## 2. Hub usage

### 2.1. Current hub hooks

Live registration: `plugin-dist/hooks/hooks.json` (source of truth). As of 2026-06-10 the hub uses **7 of the 30 events**:

| Event | Matcher | Hub scripts |
|---|---|---|
| `SessionStart` | `compact` | `feedback-nudge-compact` (harness-feedback nudge after long sessions; dev installs only — silent unless the `harness-feedback` skill is present) |
| `SessionStart` | `startup\|resume\|clear\|compact` | `session-posture`, `hooklib-smoke-check`, `telemetry` |
| `PreToolUse` | `Bash` | `path-validation`, `secret-commit-gate` (deny `git commit` that stages a high-confidence vendor token; scans `git diff --cached`/`HEAD`, skips SOPS/git-crypt repos, fail-safe defers; ADR 0079), `bash-pattern-reminder`, `commit-conventional-reminder` |
| `PreToolUse` | `Skill` | `telemetry` |
| `PostToolUse` | `Edit\|Write\|MultiEdit` | `scan-suppression-markers`, `comment-discipline-reminder`, `python-security-scan`, `python-deps-audit`, `nodejs-deps-audit`, `nodejs-security-scan`, `telemetry` (ticket-creation rate + `code_edit` domain bucket with `agent_type` attribution — denominator for profile-agent under-use) |
| `Stop` | `*` | `stop-gate-suppression-markers`, `stop-gate-comment-discipline` (process-narration comments vs HEAD, shared `_markers.flag_comment`), `python-security-stop-gate`, `nodejs-security-stop-gate`, `frontend-fsd-gate`, `frontend-dead-code`, `fallow-quality-note` (advisory: fallow analyzer на изменённых TS/JS; throttled 5 min; conservative categories only) — on dev installs every `emit_block` reason carries the `harness-feedback` nudge (`_hooklib.FEEDBACK_NUDGE`; silent on plain installs) |
| `PermissionDenied` / `SubagentStart` / `SessionEnd` | `*` | `telemetry` |

Shared scaffolding (`_hooklib.py` + `_markers.py`, stdlib-only) underlies them. The other 26 events are unused — see the opportunity map below.

### 2.2. Opportunity map — unused events (direct purpose + analytics)

Two kinds of opportunity per event: **direct** (the hook acts on the session) and **analytics** (a silent, observe-only hook that logs a fact and returns nothing — `exit 0`, no stdout — for later research). Analytics maps onto the "did the behaviour happen" facts that are otherwise only felt, not counted.

| Event | Direct-purpose candidacy | Analytics candidacy (silent log) |
|---|---|---|
| `PreToolUse` (Task / Agent) | — | **high** — sub-agent dispatch count + `agent_type` |
| `PreToolUse` (advisor) | — | **high** — advisor calls per cycle |
| `PreToolUse` (Skill) | — | high — skill activation frequency |
| `PostToolUse` (Write → `docs/tickets/`) | — | **high** — ticket-creation rate |
| existing detector hooks | (already act) | **high** — `log_event()` the incident (rule, file_ext, decision) → real FP / trivial rate |
| `UserPromptSubmit` | pre-block dangerous commands | high — turns per task |
| `SubagentStart` / `SubagentStop` | global context injection¹ | high — sub-agent lifecycle / count |
| `PreCompact` | — | med — compaction frequency (context-pressure signal) |
| `SessionStart` / `SessionEnd` | (posture already wired) | med — session bound for aggregation |
| `PermissionRequest` | programmatic allow / deny | med — permission-prompt frequency (auto-mode friction) |
| `CwdChanged` / `InstructionsLoaded` / `FileChanged` / `Worktree*` | — | low — situational |

¹ Subagent context injection carries the cross-agent caveat in §1.6 — per-agent frontmatter `hooks:` are **ignored for plugin subagents**, so a cross-agent hook must live in the global `hooks.json`.

→ The high-value analytics rows are the on-ramp for the telemetry layer (next step): they auto-count exactly the behaviours observed in real use (advisor calls, sub-agent use, tickets, incident FP rate). Measurement discipline + the behaviour-vs-quality split: project memory `structured-workflow-efficacy-evidence`.

### 2.3. Hub principles for hooks

- **Absolute paths** in `"command"`: `$HOME/.claude/hooks/...` or `${CLAUDE_PROJECT_DIR}/...`, not relative.
- **Fail-safe**: any hook error → exit 0 with no output. A hook must not break the session.
- **Self-loop guard** for the `Stop` hook: check `stop_hook_active` and exit 0.
- **Self-exclusion** for marker-detector hooks: `_SELF_FILES` whitelist, otherwise the detector flags itself.
- **Stdlib only** — no venvs or third-party deps, for fast startup.

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
