# OpenCode CLI

Consult the current [OpenCode CLI documentation](https://opencode.ai/docs/cli/) and installed `opencode run --help` before use.

Start bounded work with `opencode run <prompt> --format json --dir <project-root>`. Capture its exact session identifier and continue the same result with `opencode run <correction> --format json --dir <project-root> --session <session-id>`.

Verify current agent and permission controls separately before assigning a read-only review or implementation. Do not use `--continue` when sessions can overlap, `--fork` for a correction to the same result, `--share` implicitly, or `--auto` as a routine peer-work option. A standalone run does not require exposing a persistent server.
