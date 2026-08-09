# Independent Codex review

Use this only at the Codex checkpoint in [workflow.md](workflow.md). The purpose
is a fresh second model with different blind spots, not delegated ownership.

## Route the review

Before the first run in a session, inspect `codex exec --help` and
`codex exec resume --help`; use only models and options the installed CLI
supports. Choose the cheapest route that matches the cost of a missed blind
spot:

- bounded formal checkpoint with clear local scope and reversible consequences:
  `gpt-5.6-terra` at `medium`;
- complex, ambiguous, cross-cutting, or architectural decision:
  `gpt-5.6-sol` at `medium`;
- irreversible data, money, security, broad production impact, or
  hard-to-reverse architecture: `gpt-5.6-sol` at `xhigh`.

Do not add a `high` tier without empirical evidence that it improves these
reviews. Do not use `luna` for an independent architectural checkpoint; a task
mechanical enough for it should normally be proved by a test or a narrower
executor. Do not use `ultra`: this checkpoint needs one independent reviewer,
not another orchestration layer.

Keep the selected model and effort for every continuation. If the first result
proves that the task was under-classified, a later pass may move upward and
counts toward the same pass limit; never move downward within a review cycle.

## Run the first pass

Use a fresh, read-only run against the real repository. Put temporary briefs,
events, diagnostics, and final answers in a temporary directory outside the
repository.

Give Codex a neutral English brief containing the proposed decision, alternatives
considered, load-bearing assumptions, verified evidence, acceptance conditions,
and affected paths. Ask for grounded blind spots and a clear verdict. Require it
to inspect the repository, make no edits or commits, distinguish evidence from
inference, and report what it could not verify.

Use an absolute repository path, the routed model and reasoning effort,
read-only sandboxing, non-interactive approval, JSON events, an output file for
the final message, and closed stdin. For the installed CLI, the shape is:

```bash
codex exec -C /absolute/repository -s read-only \
  -m <model> -c 'model_reasoning_effort="<effort>"' \
  -c 'approval_policy="never"' \
  --json \
  -o /absolute/temporary/answer.md \
  "$(< /absolute/temporary/brief.md)" < /dev/null \
  > /absolute/temporary/events.jsonl \
  2> /absolute/temporary/diagnostics.log
```

Use the routed `medium` or `xhigh` value. Read the final-answer file and obtain
the exact `thread_id` from the `thread.started` JSON event; never use `--last`,
because another concurrent Codex session may be newer. Inspect only bounded
event or diagnostic excerpts when diagnosing a failure.

Verify every material finding yourself against code, sources, or an experiment
before changing the decision. Agreement is not proof, and disagreement is a
reason to investigate rather than obey either model.

The default cost is one pass. Continue only when a new finding is directly
verified as material and resolving it changes the architecture, recommendation,
DoD, red evidence, or another load-bearing assumption. If that happens, read
[codex-resume.md](codex-resume.md) before another invocation. Otherwise stop.

Do not relaunch after an interrupted wait until the process, repository state,
and recent session activity show that the prior run actually stopped. Never
include secrets in the brief or return raw logs without checking them.
