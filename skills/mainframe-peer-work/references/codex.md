# Codex CLI

Consult the current [Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) and installed `codex exec --help` before use.

Start bounded work with `codex exec --json -C <project-root> <prompt>`. For a read-only review, select the documented read-only sandbox before execution. Capture the exact session identifier from the JSONL event stream and continue the same result with `codex exec resume --json <session-id> <correction>`.

Do not use `resume --last` when sessions can overlap. Do not use `--ephemeral` when continuation is required. Keep normal approval and sandbox controls; `--dangerously-bypass-approvals-and-sandbox` is not a routine peer-work option.
