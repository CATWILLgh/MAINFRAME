# Codex CLI

Read the [official CLI documentation](https://learn.chatgpt.com/docs/non-interactive-mode) before use and recheck the relevant contracts when versions change. Examples checked against
the publisher documentation on 2026-09-05; installed versions can differ.

Use `codex exec "bounded task"` for noninteractive work; `--json` provides events. Continue the exact captured session with `codex exec resume <SESSION_ID> "correction"`. Avoid `--last` when sessions may overlap. Verify the installed CLI help for sandbox, approval, working directory, and resume-specific options. Select restrictions before execution; an unattended run cannot rely on an interactive approval prompt.

Use an already authorized native login; never inspect credential files. If
authentication or installation is missing, report the exact operator step.
Capture the session identifier from documented output, wait for completion,
and verify the result and assigned files. Exit status alone is insufficient.
