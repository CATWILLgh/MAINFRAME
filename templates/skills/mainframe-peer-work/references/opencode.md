# OpenCode CLI

Read the [official CLI documentation](https://opencode.ai/docs/cli/) before use and recheck the relevant contracts when versions change. Examples checked against
the publisher documentation on 2026-09-05; installed versions can differ.

Use `opencode run "bounded task" --format json`. Continue with `opencode run --session <SESSION_ID> "correction"`. The run command supports model and agent selection; confirm current permissions separately. Do not enable automatic approval or session sharing by default. A standalone run does not require starting a separately managed public server. Check the binary generation: these examples describe `opencode`, not `opencode2`.

Use an already authorized native login; never inspect credential files. If
authentication or installation is missing, report the exact operator step.
Capture the session identifier from documented output, wait for completion,
and verify the result and assigned files. Exit status alone is insufficient.
