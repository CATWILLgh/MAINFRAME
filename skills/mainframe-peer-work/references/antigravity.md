# Antigravity CLI

Consult the current [Antigravity headless-mode documentation](https://antigravity.google/docs/cli/headless/) and installed `agy --help` before use.

Start bounded work with `agy -p <prompt> --output-format json`. Capture `conversation_id` from the result and continue the same result with `agy -p <correction> --output-format json --conversation <conversation-id>`.

Select the current documented execution mode, sandbox, agent, and permissions before running. In a review-oriented mode, a denied approval may still leave a superficially successful process result, so inspect tool diagnostics and the actual deliverable. Do not use `--continue` when conversations can overlap or `--dangerously-skip-permissions` as a routine peer-work option.
