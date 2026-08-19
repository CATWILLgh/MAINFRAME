---
name: mainframe-peer-review
description: Ask the separately installed Codex CLI for one bounded independent review of a consequential decision or completed implementation. Use only at an explicit MAINFRAME review checkpoint; never use it for implementation, ordinary second opinions, or when the Codex peer integration was not installed.
allowed-tools: Bash(codex *), Bash(mktemp *), Bash(rm *), Read, Write
---

# Independent Codex review

Use Codex only to expose blind spots. The primary Claude session keeps
ownership, verifies every material finding, and decides what changes.

## Prepare

Inspect `codex exec --help` and `codex exec resume --help`. Create a temporary
directory outside the repository and write a neutral English brief with the
decision or final state, alternatives, load-bearing assumptions, verified
evidence, acceptance conditions, and affected paths. Exclude secrets and
unrelated transcript content.

Use `gpt-5.6-sol` with `medium` reasoning for complex, ambiguous, cross-cutting,
or architectural work. Use `xhigh` only for irreversible data, money, security,
broad production impact, or hard-to-reverse architecture.

## Run

```bash
codex exec --ignore-user-config --strict-config \
  -C /absolute/repository -s read-only -m <model> \
  -c 'model_reasoning_effort="<effort>"' -c 'approval_policy="never"' --json \
  -o /absolute/temporary/answer.md \
  "$(< /absolute/temporary/brief.md)" < /dev/null \
  > /absolute/temporary/events.jsonl 2> /absolute/temporary/diagnostics.log
```

Read the final answer and obtain the exact `thread_id` from `thread.started`;
never use `--last`. Treat a missing answer, failed process, or malformed event
stream as unavailable, not approval. Verify every material finding before
changing the decision.

Resume only when a newly verified material finding changes architecture,
recommendation, definition of done, or load-bearing evidence. Send the revised
package and a concise factual delta to the exact thread:

```bash
codex exec resume --ignore-user-config --strict-config <thread-id> -m <model> \
  -c 'model_reasoning_effort="<effort>"' -c 'sandbox_mode="read-only"' \
  -c 'approval_policy="never"' --json -o /absolute/temporary/answer-2.md \
  "$(< /absolute/temporary/follow-up-2.md)" < /dev/null \
  > /absolute/temporary/events-2.jsonl 2> /absolute/temporary/diagnostics-2.log
```

Allow at most three completed passes, keep model and reasoning stable unless a
verified result proves under-classification, and never downgrade within a
cycle. Remove temporary artifacts after reconciliation. Codex is an
independent input, never the final authority.
