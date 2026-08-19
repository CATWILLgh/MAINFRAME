---
name: mainframe-peer-review
description: Ask the separately installed and authenticated Claude Code CLI for one bounded independent review of a consequential decision or completed implementation. Use only at an explicit MAINFRAME review checkpoint; never use it for implementation, ordinary second opinions, or when the Claude peer integration was not installed.
---

# Independent Claude review

Use Claude only to expose blind spots. The primary Codex task keeps ownership,
verifies every material finding, and decides what changes.

## Prepare

Confirm `claude --version` and `claude auth status >/dev/null` succeed without
printing account data. Create a temporary directory outside the repository.
Write a neutral English brief containing the decision or final state, alternatives,
load-bearing assumptions, verified evidence, acceptance conditions, and exact
paths Claude may inspect. Exclude secrets and unrelated conversation history.

Use `opus` with `high` effort. Raise effort to `xhigh` only for irreversible
data, money, security, broad production impact, or hard-to-reverse architecture.

## Run

Inspect `claude --help` before relying on syntax. Start a new, persistent print
session in the repository with customizations disabled and only read/search
tools available:

```bash
claude -p --safe-mode --permission-mode dontAsk \
  --tools "Read,Grep,Glob,WebSearch,WebFetch" \
  --model opus --effort <effort> --output-format json \
  "$(< /absolute/temporary/brief.md)" \
  > /absolute/temporary/result.json
```

Read `result` and the exact `session_id` from the JSON. Treat a non-success
subtype, permission denial, missing result, or invalid JSON as unavailable, not
as approval. Verify findings against the repository, tests, or current primary
sources before acting.

Resume only after a newly verified material finding changes the decision,
architecture, definition of done, or evidence. Send a concise factual delta to
the exact session with `claude -p --resume <session-id>` and the same model,
effort, safe mode, permission mode, tools, and JSON output. Allow at most three
completed review passes. Never downgrade within a cycle, retry endlessly, or
use `--dangerously-skip-permissions`.

Remove temporary artifacts after reconciliation. Report Claude as an
independent input, never as the final authority.
