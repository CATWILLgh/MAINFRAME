# Independent Codex review

Use this only at the Codex checkpoint in [workflow.md](workflow.md). It provides
a second model's blind spots, not delegated ownership.

## Route

Inspect `codex exec --help` and `codex exec resume --help`; use only supported
options. Choose by the cost of a missed issue:

- bounded formal, local, reversible: `gpt-5.6-terra`, `medium`;
- complex, ambiguous, cross-cutting, architectural: `gpt-5.6-sol`, `medium`;
- irreversible data, money, security, broad production, or hard-to-reverse
  architecture: `gpt-5.6-sol`, `xhigh`.

Do not add `high` without evidence that it improves these reviews. Do not use
`luna` for architectural judgment or `ultra` to add another orchestration layer.
Keep model and effort across passes unless a result proves under-classification;
an upgrade counts as a pass. Never downgrade within a review cycle.

## First pass

Create a temporary directory outside the repository. Give Codex a neutral
English brief with the decision, alternatives, load-bearing assumptions,
verified evidence, acceptance conditions, and affected paths. Ask for grounded
blind spots and a verdict. Require repository inspection, read-only behavior,
evidence/inference separation, and explicit unverifiable claims.

```bash
codex exec -C /absolute/repository -s read-only -m <model> \
  -c 'model_reasoning_effort="<effort>"' -c 'approval_policy="never"' --json \
  -o /absolute/temporary/answer.md \
  "$(< /absolute/temporary/brief.md)" < /dev/null \
  > /absolute/temporary/events.jsonl 2> /absolute/temporary/diagnostics.log
```

Read the final answer and obtain the exact `thread_id` from `thread.started`;
never use `--last`, because another session may be newer. Verify each material
finding against code, sources, or an experiment before changing the decision.

## Conditional continuation

One pass is the default. Resume only when the previous pass produced a new,
directly verified material finding whose resolution changed architecture,
recommendation, DoD, red evidence, or another load-bearing assumption. Wording,
known tradeoffs, unsupported findings, and materially identical changes do not
qualify.

Send the revised neutral package plus a concise factual delta. Ask only for new
or reintroduced material blind spots, not settled analysis without new evidence.

```bash
codex exec resume <thread-id> -m <model> \
  -c 'model_reasoning_effort="<effort>"' -c 'sandbox_mode="read-only"' \
  -c 'approval_policy="never"' --json -o /absolute/temporary/answer-2.md \
  "$(< /absolute/temporary/follow-up-2.md)" < /dev/null \
  > /absolute/temporary/events-2.jsonl 2> /absolute/temporary/diagnostics-2.log
```

Stop when no new verified material blind spot remains. Allow at most three
completed passes; a run that produced no review is not a pass, but diagnose it
before retrying. Never launch a fourth. Resolve any remainder directly and give
the package to the preparation `advisor`; without its confirmation, do not seek
agreement.

After interruption, prove the process stopped before relaunching. Keep secrets
out of briefs and inspect only bounded diagnostic excerpts.
