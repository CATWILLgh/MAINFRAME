# Continue an independent Codex review

Read this only after [codex-exec.md](codex-exec.md) produced a directly verified
material finding whose resolution changed the decision package.

Resume the exact review thread with the revised neutral package and a concise
factual delta. Ask Codex to inspect the current repository, verify the revision,
and report only new or reintroduced material blind spots. Do not repeat settled
analysis without new contradictory evidence. Unsupported findings, wording
improvements, known tradeoffs, and materially identical revisions do not
justify a continuation.

Keep the prior model and effort unless the result proved the task was
under-classified; an upgrade counts as another pass. Never downgrade. Use the
exact `thread_id`, not `--last`, and preserve read-only safety explicitly:

```bash
codex exec resume <thread-id> \
  -m <model> -c 'model_reasoning_effort="<effort>"' \
  -c 'sandbox_mode="read-only"' \
  -c 'approval_policy="never"' \
  --json \
  -o /absolute/temporary/answer-2.md \
  "$(< /absolute/temporary/follow-up-2.md)" < /dev/null \
  > /absolute/temporary/events-2.jsonl \
  2> /absolute/temporary/diagnostics-2.log
```

After each continuation, verify every new material finding directly. Stop when
there is no new verified material blind spot. Allow at most three completed
passes in one preparation cycle. A launch, authentication, or transport failure
that produced no review is not a completed pass, but diagnose it before retrying.

After the third completed pass, never launch a fourth. Resolve any remaining
finding directly and give the resulting package to the required `advisor` at
the end of preparation. If the advisor cannot confirm readiness, do not present
the package for agreement.
