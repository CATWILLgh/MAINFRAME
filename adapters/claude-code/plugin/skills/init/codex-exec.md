# Independent Codex review

Use this only at the Codex checkpoint in [workflow.md](workflow.md). The purpose
is a fresh second model with different blind spots, not delegated ownership.

Before the first run in a session, inspect `codex exec --help` and choose an
available strong model explicitly. Use a fresh, read-only run against the real
repository. Put temporary briefs, logs, and the final answer in a temporary
directory outside the repository.

Give Codex a neutral English brief containing the proposed decision, alternatives
considered, load-bearing assumptions, verified evidence, acceptance conditions,
and affected paths. Ask for grounded blind spots and a clear verdict. Require it
to inspect the repository, make no edits or commits, distinguish evidence from
inference, and report what it could not verify.

Use an absolute repository path, explicit model and reasoning effort, read-only
sandboxing, non-interactive approval, an output file for the final message, and
closed stdin. For the installed CLI, the shape is:

```bash
codex exec -C /absolute/repository -s read-only \
  -m <model> -c 'model_reasoning_effort="high"' \
  -c 'approval_policy="never"' \
  -o /absolute/temporary/answer.md \
  "$(< /absolute/temporary/brief.md)" < /dev/null \
  > /absolute/temporary/codex.log 2>&1
```

Read the final-answer file; inspect only bounded parts of the event log when
diagnosing a failure. Verify every material finding yourself against code,
sources, or an experiment before changing the decision. Agreement is not proof,
and disagreement is a reason to investigate rather than obey either model.

Do not relaunch after an interrupted wait until the process, repository state,
and recent session activity show that the prior run actually stopped. Never
include secrets in the brief or return raw logs without checking them.
