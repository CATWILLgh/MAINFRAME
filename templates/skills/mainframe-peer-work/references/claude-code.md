# Claude Code CLI

Read the [official CLI documentation](https://code.claude.com/docs/en/cli-usage) before use and recheck the relevant contracts when versions change. Examples checked against
the publisher documentation on 2026-09-05; installed versions can differ.

Use `claude -p "bounded task" --output-format json`. Continue the captured session with `claude -p --resume <SESSION_ID> "correction"`. Verify current tool-selection and permission options against CLI help before applying them. Distinguish available tools from permission rules; a request to review is not an enforced read-only boundary.

Use an already authorized native login; never inspect credential files. If
authentication or installation is missing, report the exact operator step.
Capture the session identifier from documented output, wait for completion,
and verify the result and assigned files. Exit status alone is insufficient.
