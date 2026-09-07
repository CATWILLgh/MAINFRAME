# Claude Code CLI

Consult the current [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference) and installed `claude --help` before use.

Start bounded work with `claude -p <prompt> --output-format json`. Capture the returned session identifier and continue the same result with `claude -p --resume <session-id> <correction> --output-format json`. Use `--background` only under the agreed background posture and use the native background-session commands to attach, inspect completion, or stop it.

Map read-only work through current documented tool and permission restrictions; a prompt saying "review" is not enforcement. Do not use `--continue` when sessions can overlap, `--no-session-persistence` when continuation is required, or `--dangerously-skip-permissions` as a routine peer-work option.
