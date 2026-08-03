# Local agent surfaces: live verification runbook

This runbook is the acceptance gate for MAINFRAME on local Codex and the three
official local Claude Code surfaces: CLI, the official VS Code extension, and
Desktop Code Local. Cloud runs, Cowork, OpenCode, and Antigravity are outside
this gate.

Repository tests prove build and filesystem behavior. They cannot prove that a
running host refreshed its skill registry after an update, so activation and
the session checks below happen in one explicit live-test window.

## Before activation

1. Run the full repository verification recorded in
   [`docs/delivery-readiness.md`](delivery-readiness.md).
2. Build Claude and Codex bundles into temporary directories. Do not publish to
   `dist/` while it is linked into a running host.
3. Confirm the only remaining source/render mismatch is the reviewed release
   candidate.
4. Close all Claude Code and Codex sessions that may retain the previous
   registry.

## Activation boundary

Publishing `dist/claude-code` or `dist/codex` can immediately affect a running
host through existing symbolic links. Treat rendering and `./install.sh
--codex` as the start of the live window, not as a preparatory dry run.

Immediately after activation, run the value-free layout check:

```bash
.venv/bin/python3 tools/check_local_agent_surfaces.py
```

It checks binary availability, Claude plugin skill files, Codex public skills,
Codex private agent methods, and generated agent instructions. It does not read
credential values or modify either configuration directory.

## One marker prompt

Use the same harmless prompt in every host:

> Load the MAINFRAME `surface-ticket` skill, report only its title and whether
> it loaded successfully, and do not create or edit a ticket.

This tests real skill resolution without using slash-menu visibility as a
proxy. `surface-ticket` is intentionally absent from the user command menu but
must remain available to the main agent.

For a designated-agent check, ask a specialized agent to state the heading of
its private method without changing files. In Codex, the main agent must not
list that private method as a global skill; the specialized agent must still
receive it.

## Session matrix

Record host version, session identifier where exposed, result, and exact error
text for every row.

| Host | Fresh | Same long session | Resumed | After compaction |
|---|---:|---:|---:|---:|
| Claude Code CLI | required | required | required | required |
| Official VS Code extension | required | required | required | required |
| Desktop Code Local | required | required | required | required |
| Codex local app/CLI | required | required | required | required |

For Claude Code CLI, start with `claude`, keep the session open for the second
probe, use `/compact` for the compaction probe, then exit and reopen it with
`claude --resume <session-id>` for the resume probe. The CLI officially
supports `--continue`, `--resume`, print mode, and structured output; use the
interactive path here because the skill tool itself is the behavior under
test. See the [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
and [session management documentation](https://code.claude.com/docs/en/sessions).

Run the VS Code and Desktop rows inside their own interfaces. Do not reuse a
CLI result for them: the official VS Code integration has its own conversation
surface and history. See the [official VS Code guide](https://code.claude.com/docs/en/vs-code)
and [Desktop guide](https://code.claude.com/docs/en/desktop).

## Pass and rollback rules

The live gate passes only when every required row resolves the marker and every
designated-agent check preserves private-method isolation. `plugin list`, valid
manifests, and correct files are supporting evidence, not substitutes.

On `Unknown skill`, missing private method, or a host-specific mismatch:

1. record the host, version, session transition, and exact error;
2. do not retry by changing multiple variables;
3. restore the previous immutable release through the release lifecycle;
4. keep tickets `f9d6a8b0` and `7e88d75a` open until the failing row is
   reproduced and fixed.
