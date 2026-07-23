---
name: harness-feedback
user-invocable: true
description: File a structured feedback report about friction caused by the mainframe harness itself — a hook gate block that looks like a false positive, a permission rule that denied legitimate work, a skill or rule instruction that proved unclear or contradictory, or a capability the harness lacks. Writes one Markdown file with YAML frontmatter (date/project/session/artifact/type/severity/title) and a mandatory `## Trigger` section into the adapter-local `{{mainframe.feedback_dir}}` queue via the bundled `feedback.py` receiver; the hub processes the queue as candidates and tunes the harness. Friction-only channel — not for praise, not for problems in the project's own code (that is `surface-ticket`), and filing feedback never replaces fixing a gate finding.
when_to_use: Trigger when the harness itself — not the project — got in the way and the friction is concrete and reproducible — a stop-gate or scan hook flagged correct code (false positive), an auto-mode permission rule denied or stalled legitimate work, a global rule or skill instruction proved ambiguous or contradictory in practice, or a needed harness capability is missing. File AFTER resolving the block or finishing the workaround, never instead of it; one report per distinct friction, not per occurrence.
---

# Harness feedback

The feedback channel for the mainframe harness (global instructions, plugin skills, hooks, agents, permission rules). Telemetry already counts events; this skill carries the *meaning* — what blocked you, why it was wrong, what would fix it. Reports land in `{{mainframe.feedback_dir}}` and are processed by the hub as candidates, not as truths. The receiver requires `feedback: true` in `{{mainframe.diagnostics_config}}`.

**Non-waiver rule:** feedback never unblocks anything. A gate finding still gets fixed (or explicit user permission obtained); a denied command still goes through the permission flow. File feedback after the friction is handled.

## How to file

Run the receiver bundled with this skill ([feedback.py](feedback.py) in this skill's base directory), body on stdin:

```sh
python3 "<this skill's base dir>/feedback.py" \
  --artifact "<hub artifact, exact name>" \
  --type <false-positive|friction|unclear-instruction|missing-capability|other> \
  --severity <low|medium|high> \
  --title "<one line>" <<'EOF'
## Trigger
<the EXACT command / tool call / file+line / gate label that hit the friction>

## Expected vs actual
<what should have happened vs what happened>

## Suggestion
<optional: concrete change that would have prevented it>
EOF
```

The script validates the type, requires the `## Trigger` section, and prints the written path. It warns (but still writes) past 5 reports from one project per day — consolidate instead of repeating.

**Body quotes a flagged keyword?** Permission rules glob the whole Bash command string, data included — a body QUOTING a destructive pattern (SQL drop/truncate statements, recursive-delete commands) gets the heredoc call itself denied. Do not reword the quote away; write the body to a scratch file with the Write tool first, then feed it by path: `python3 "<skill dir>/feedback.py" --artifact ... < /path/to/body.md` — the command line then carries only the path.

## Types

| type | use when |
|---|---|
| `false-positive` | a detector / gate / scan flagged correct code or a legitimate command |
| `friction` | the harness worked as designed but cost real time or forced a workaround |
| `unclear-instruction` | a rule / skill text was ambiguous, contradictory, or misleading in practice |
| `missing-capability` | the harness lacks something the task genuinely needed |
| `other` | real harness friction that fits none of the above |

## Concreteness requirements

- `--artifact` names the exact hub artifact: the gate label from the block message (e.g. `python-security-stop-gate`), the permission rule pattern, the skill or rule name. Unsure — closest name + say so in the body.
- `## Trigger` quotes the exact command, tool call, or file/line that fired it. A report that cannot be reproduced from its Trigger is noise.
- Severity honestly: `high` only when the friction blocked or corrupted real work.

## What NOT to file

- Problems in the project's own code or tests → `surface-ticket`.
- Praise / "worked well" notes — this channel is friction-only by design.
- Secrets, tokens, whole file dumps — quote the minimal excerpt that reproduces.
- A second report for the same friction in the same session — update nothing, it is already queued.
