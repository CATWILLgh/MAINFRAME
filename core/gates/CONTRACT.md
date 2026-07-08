# Gate wire contract

A gate detector is a standalone `python3` script (stdlib-first) that reads one
JSON payload from stdin and answers on stdout. This shape originates from
Claude Code's hook I/O and is adopted as the hub's interchange format: it
already has two consumers (Claude Code natively; OpenCode through the
dispatcher plugin, which translates OpenCode tool calls into this payload and
parses the response). A new tool adapter translates to/from this contract —
it does not get a new one.

## Input (stdin JSON)

| Field | Meaning |
|---|---|
| `tool_name` | Tool being gated (`Bash`, `Edit`, `Write`, …) |
| `tool_input` | Tool arguments (`command`, `file_path`, `content`, …) |
| `cwd` | Session working directory |
| `project_dir` | Optional. Project root for callers without the Claude Code env contract; a detector prefers it over `$CLAUDE_PROJECT_DIR`, falling back to `cwd` |
| `hook_event_name`, `stop_hook_active`, … | Event-specific fields as sent by the host tool |

## Output (stdout JSON, exit code always 0)

- Pre-tool verdicts: `{"hookSpecificOutput": {"hookEventName": …,
  "permissionDecision": "allow"|"ask"|"deny", "permissionDecisionReason": …}}`
- Advisory notes: `hookSpecificOutput.additionalContext` (reaches the model),
  `systemMessage` (reaches the user).
- Stop gates: `{"decision": "block", "reason": …}`.
- Silence (no stdout) = no opinion.

Blocking happens ONLY via JSON. A nonzero exit is an infrastructure failure by
construction; the Claude Code adapter's `run-hook.sh` converts it into a loud
no-op instead of an accidental block (see its header for the incident that
forced this).

## Runtime layout expectations

- All detectors and their `_`-prefixed shared libs are deployed into ONE flat
  directory: bare sibling imports (`from _hooklib import …`) must resolve.
- `rules/` (detector data, e.g. semgrep rules) deploys as a sibling directory
  of the scripts dir.
- Detectors must stay runnable as bare scripts with no hub-specific env;
  everything they need arrives in the payload or sits next to them.
