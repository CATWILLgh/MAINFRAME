---
name: harness-feedback
description: Record one concrete reproducible problem caused by the MAINFRAME harness itself while the Codex adapter is installed in development mode. Use after resolving the immediate block for hook false positives, permission friction, unclear instructions, or a missing harness capability; not for project defects, praise, or routine status reporting.
---

# Harness feedback

Record what Codex encountered, not a general opinion. Reports go to the Codex
adapter's private development queue and are candidates for later review. Filing
never waives a gate, changes policy, or replaces completing the active task.

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
