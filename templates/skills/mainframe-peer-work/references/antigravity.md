# Antigravity CLI

Read the [official CLI documentation](https://antigravity.google/docs/cli/headless/) before use and recheck the relevant contracts when versions change. Examples checked against
the publisher documentation on 2026-09-05; installed versions can differ.

Use `agy -p "bounded task" --output-format json`. Continue the exact conversation with `--conversation <ID>`, not the most recent conversation. Under request-review, headless tools needing approval may be denied while the process still exits successfully. Inspect diagnostics and actual task completion. Verify documented scoped permissions and timeout options before running. Do not substitute Gemini CLI commands or disable permission checks by default.

Use an already authorized native login; never inspect credential files. If
authentication or installation is missing, report the exact operator step.
Capture the session identifier from documented output, wait for completion,
and verify the result and assigned files. Exit status alone is insufficient.
