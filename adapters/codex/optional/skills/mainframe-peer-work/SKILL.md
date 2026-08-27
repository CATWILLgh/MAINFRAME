---
name: mainframe-peer-work
description: Run a bounded Claude Code CLI session for independent review or implementation when another model can usefully check or execute one agreed block. Continue the same session for corrections to the same result; start a new session after acceptance or a scope change.
---

# Claude peer session

Use Claude Code as either an independent reviewer or a bounded implementation
peer. The current Codex task owns scope, user communication, verification, and
acceptance. A peer implementation changes the same checkout; inspect its diff
and evidence before accepting it.

## Choose the session route

- Use `new` for a new agreed result, a different worktree, or work whose prior
  peer session has already been accepted.
- Use `resume` for feedback, missing work, or another review pass on the same
  agreed result in the same checkout. Resume the exact returned session ID so
  Claude keeps its repository context.
- Do not run two implementation peers in the same checkout concurrently.

Write a bounded English request to a temporary file. Include the result to
produce, relevant constraints and evidence, allowed scope, acceptance checks,
and whether Claude should review or implement. Exclude secrets and unrelated
conversation history.

```bash
mainframe-claude new --role <review|implement> \
  --project /absolute/repository --request /absolute/request.md \
  --model <model> [--effort <effort>] [--access <auto|full>]
```

The launcher returns immediately. Do not poll it. End the current turn when no
other useful work remains; the optional Codex Stop bridge waits outside the
model loop and continues this task once with Claude's result.

For corrections or another review pass on the same result:

```bash
mainframe-claude resume --session <session-id> \
  --project /absolute/repository --request /absolute/follow-up.md
```

The launcher preserves the original model, effort, role, and access on resume
unless model or effort is explicitly raised. A review is always read/search
only. `auto` is the implementation default. Use `full` only when the user
already authorized that wider local access.

## Model and effort matrix

Use `medium` by default and preserve the same selection throughout one peer
cycle. Do not use `ultracode`.

| Work | Model and effort |
|---|---|
| Narrow mechanical inspection with no important judgment | `haiku`; omit `--effort` because effort is not supported |
| Ordinary bounded implementation | `sonnet`, `medium` |
| Complex implementation or architecture-sensitive review | `opus`, `medium` |
| Difficult debugging, security, data integrity, or hard-to-reverse design | `opus`, `high`; use `xhigh` only after a real need is shown |
| Exceptional quality-first retry after lower effort was insufficient | `opus`, `max` |
| Large-context alternative when its different attention pattern is useful | `fable`, `medium` |

After the bridge returns, inspect the peer result, actual changes, and checks.
Verify every material claim. Resume for corrections to this result; otherwise
finish the cycle and use `new` for the next result.
