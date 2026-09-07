# Pi CLI

Consult the current [Pi CLI documentation](https://pi.dev/docs/latest/) and installed `pi --help` before use. Use [Pi session documentation](https://pi.dev/docs/latest/sessions) when exact continuation behavior matters.

Start bounded work with `pi -p --mode json <prompt>` in the exact project root. Capture the session identifier from machine-readable output, or select an explicit project session identity through the current documented session option. Continue the same result with `pi -p --mode json --session <session-id-or-path> <correction>`.

For a read-only review, use the native tool allowlist, such as the currently documented read-only `read`, `grep`, `find`, and `ls` tools, after verifying the installed names. Do not use `--continue` when sessions can overlap, `--no-session` when continuation is required, or enable write and shell tools for a read-only assignment.
