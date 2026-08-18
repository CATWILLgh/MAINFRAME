---
name: harness-feedback
user-invocable: true
description: File one structured report when the MAINFRAME harness itself causes concrete reproducible friction in Claude Code development mode. Use after resolving the immediate block for hook false positives, permission friction, unclear instructions, or a missing harness capability; not for project defects or praise.
when_to_use: Use only when MAINFRAME itself got in the way and the trigger can be named exactly. Finish or unblock the current task first, then file one report per distinct problem.
---

# Harness feedback

Record what Claude Code encountered, not a general opinion. Reports go to the
Claude adapter's private development queue and are candidates for later review.
Filing never waives a gate or replaces fixing the active task. Optional Spark
analysis may start after the durable write; it never changes the command result.

Run [feedback.py](feedback.py) from this skill directory with the report body on
stdin:

```sh
python3 "<this skill's base dir>/feedback.py" \
  --artifact "<exact hook, rule, skill, or agent>" \
  --type <false-positive|friction|unclear-instruction|missing-capability|other> \
  --severity <low|medium|high> \
  --title "<one line>" <<'EOF'
## Trigger
<exact command, tool call, or file and line>

## Expected vs actual
<what should have happened and what happened>

## Suggestion
<optional bounded improvement>
EOF
```

Do not include secrets, whole files, praise, or project-code defects. If a
quoted command would itself trigger a permission rule, write the body with the
file-writing tool and redirect that file into the receiver.
