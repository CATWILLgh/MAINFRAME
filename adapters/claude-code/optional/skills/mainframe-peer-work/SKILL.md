---
name: mainframe-peer-work
description: Run a bounded Codex CLI session for independent review or implementation when another model can usefully check or execute one agreed block. Continue the same session for corrections to the same result; start a new session after acceptance or a scope change.
allowed-tools: Bash(mainframe-codex *), Bash(mktemp *), Bash(rm *), Read, Write
---

# Codex peer session

Use Codex as either an independent reviewer or a bounded implementation peer.
The current Claude session owns scope, user communication, verification, and
acceptance. A peer implementation changes the same checkout; inspect its diff
and evidence before accepting it.

## Choose the session route

- Use `new` for a new agreed result, a different worktree, or work whose prior
  peer session has already been accepted.
- Use `resume` for feedback, missing work, or another review pass on the same
  agreed result in the same checkout. Resume the exact returned session ID so
  Codex keeps its repository context.
- Do not run two implementation peers in the same checkout concurrently.

Write a bounded English request to a temporary file. Include the result to
produce, relevant constraints and evidence, allowed scope, acceptance checks,
and whether Codex should review or implement. Exclude secrets and unrelated
conversation history.

Launch the command as a background Bash task. Let Claude Code deliver its
native completion notification; do not poll it with repeated model turns.

```bash
mainframe-codex new --role <review|implement> \
  --project /absolute/repository --request /absolute/request.md \
  --model <model> --effort <effort> [--access <auto|full>]
```

For another pass on the same result:

```bash
mainframe-codex resume --session <session-id> \
  --project /absolute/repository --request /absolute/follow-up.md
```

The launcher preserves the original model, effort, role, and access on resume
unless model or effort is explicitly raised. A review is always read-only.
`auto` is the implementation default. Use `full` only when the caller already
authorized that wider local access.

## Model and reasoning matrix

Use `medium` by default. Increase reasoning only when the task itself needs it;
do not use `ultra`.

| Work | Model and effort |
|---|---|
| Narrow mechanical inspection or tiny edit | `gpt-5.6-luna`, `low` |
| Ordinary bounded implementation or review | `gpt-5.6-terra`, `medium` |
| Complex cross-cutting implementation or architecture-sensitive review | `gpt-5.6-sol`, `medium` |
| Difficult debugging, security, data integrity, or hard-to-reverse design | `gpt-5.6-sol`, `high`; use `xhigh` only after a real need is shown |
| Exceptional quality-first retry after lower effort was insufficient | `gpt-5.6-sol`, `max` |
| Compatibility fallback when the 5.6 family is unavailable | `gpt-5.5`, `medium` |

After completion, read the returned answer and session ID, inspect actual
changes and checks, and verify every material claim. Resume for corrections to
this result; otherwise finish the cycle and use `new` for the next result.
