# Layer: Hooks

> Scripts executed by Claude Code on specific events (tool-use, stop, session-start, file-change, etc.). In the hub: `export/hooks/*.py` + registration in `export/settings.json` `hooks.*`.

> Last updated: 2026-05-28 (3-section rewrite after subagent deep-dive: 16 event types).

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

### 1.1. Full event list (Python SDK)

Source: `code.claude.com/docs/en/agent-sdk/python` + `code.claude.com/docs/en/hooks`.

| Event | Trigger | Matcher | Decision control | Notes |
|---|---|---|---|---|
| `PreToolUse` | Before tool execution | yes (tool name) | allow / deny / ask / defer | Can modify `updatedInput` |
| `PostToolUse` | After successful tool | yes (tool name) | block | Can modify `updatedToolOutput` |
| `PostToolUseFailure` | After failed tool | yes (tool name) | context-only | `additionalContext` |
| `UserPromptSubmit` | Prompt submitted | — | block | Receives `prompt` |
| `Stop` | Claude finishes a turn | **no matcher** | `{"decision":"block","reason":...}` | `stop_hook_active` guard |
| `SubagentStop` | Subagent finishes | yes (`agent_type`) | block / continue:false | |
| `SubagentStart` | Subagent starts | yes (`agent_type`) | context-only | Global context injection |
| `SessionStart` | Session begins | yes (`source`: startup/resume/clear/compact) | context-only | |
| `SessionEnd` | Session ends | yes (`reason`) | **cannot block** | Cleanup only |
| `Notification` | Notification triggered | yes (type) | context-only | |
| `PreCompact` | Before compaction | — | — | Payload schema not detailed |
| `PostCompact` | After compaction | — | — | Same |
| `Setup` | Session setup | — | — | Payload not detailed |
| `FileChanged` | File changed | yes (pattern) | — | Live file watching |
| `ConfigChange` | `settings.json` changed | yes (empty = all) | — | Fires on hot-reload |
| `PermissionRequest` | Permission prompt triggered | yes (tool name) | allow/deny + `updatedPermissions` | Can change mode |

The TypeScript SDK supports additional events; the full list is not published in the available docs.

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

## 2. Hub usage

### 2.1. Current hooks in `export/hooks/`

| File | Event | Status |
|---|---|---|
| `scan-suppression-markers.py` | `PostToolUse` (Edit\|Write\|MultiEdit) | LIVE via symlink |
| `stop-gate-suppression-markers.py` | `Stop` | **STAGED** — not activated, awaiting user approval |

### 2.2. Used vs unused events

| Event | In use? | If not — candidate? |
|---|---|---|
| `PostToolUse` | yes (scan-suppression-markers) | — |
| `Stop` | staged (stop-gate-suppression-markers) | — |
| `UserPromptSubmit` | no | yes — blocking dangerous commands before submission |
| `SubagentStart` | no | yes — injecting global context into each subagent |
| `SessionStart`, `SessionEnd`, `PreToolUse`, `Notification`, `FileChanged`, `ConfigChange`, `PermissionRequest` | no | maybe — no concrete use case defined yet |
| `PreCompact`, `PostCompact`, `Setup`, `PostToolUseFailure` | no | maybe — payload unclear, needs further investigation |

### 2.3. Hub principles for hooks

- **Absolute paths** in `"command"`: `$HOME/.claude/hooks/...` or `${CLAUDE_PROJECT_DIR}/...`, not relative.
- **Fail-safe**: any hook error → exit 0 with no output. A hook must not break the session.
- **Self-loop guard** for the `Stop` hook: check `stop_hook_active` and exit 0.
- **Self-exclusion** for marker-detector hooks: `_SELF_FILES` whitelist, otherwise the detector flags itself.
- **Stdlib only** — no venvs or third-party deps, for fast startup.

---

## 3. Gray zones / open questions

1. **Full TypeScript SDK event list** — it is mentioned that TS supports additional events; the list is not published.
2. **Exact size of "brief delay"** for the file watcher — not documented.
3. **Symlink behavior** for `settings.json` with the file watcher — works empirically (the hub relies on it), but without a formal smoke test.
4. **Payload schema for `Setup`, `PreCompact`, `PostCompact`, `SessionEnd`** — not explicitly provided in the available Context7 fragments. Needs further verification before use.
5. **`Stop` hook behavior after 8 consecutive blocks** — the override happens automatically. What if the hook needs to fire more frequently? No workaround is documented.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/hooks` — payload schemas, decision-control.
- `code.claude.com/docs/en/hooks-guide` — patterns, examples, matchers.
- `code.claude.com/docs/en/agent-sdk/python` — `HookEvent` type list.
- `code.claude.com/docs/en/agent-sdk/typescript` — TS-specific types.
