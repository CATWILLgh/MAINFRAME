---
id: bce23629
title: Validate the generated plugin in a live Antigravity 2.x desktop session
status: open
priority: medium
component: antigravity-2
discovered: 2026-07-15
discovered-from: []
tags: ["integration", "hooks", "memory"]
---

# bce23629: Validate the generated plugin in a live Antigravity 2.x desktop session

## What was observed

The adapter is verified against the public plugin and hook schemas, the installed
application bundle, and isolated contract tests. It was not installed into
`~/.gemini/config/plugins/mainframe` during implementation because this
repository explicitly prohibits running `install.sh` or creating delivery
symlinks without a separate user request.

## Why it is a problem

Schema tests cannot prove that the desktop application discovers the generated
global plugin, resolves its hook command, or invokes all five lifecycle events
in the expected order. A packaging or host-integration mismatch could leave the
adapter partially or completely inactive while its local tests remain green.

## Why it is not a duplicate

No existing ticket covers live Antigravity 2.x plugin activation.

## What probably needs to be done

After explicit installation approval:

1. Run the Antigravity builder with native validation and install through
   `./install.sh --antigravity-2`.
2. Restart the standalone desktop application and confirm the `mainframe`
   plugin, rules, and skills are visible.
3. Exercise `PreInvocation`, `PreToolUse`, `PostToolUse`, `PostInvocation`, and
   `Stop` with observable fixtures, including memory load and reminder paths.
4. Start the CLI separately and confirm desktop hooks ignore its
   `~/.gemini/antigravity-cli` transcript path.
5. Run the uninstall dry run and real uninstall after the probe if the user does
   not want the adapter left active.

## Acceptance criteria

- The desktop application loads the generated plugin after restart.
- Each of the five documented hook events produces the expected translated
  result without duplicate memory injection or reminder loops.
- A repository worktree recalls the same Antigravity memory as its main worktree.
- Antigravity CLI activity receives no desktop-adapter hook effects.
- Installation and uninstall preserve user customizations and memory data.

## Sources

- `adapters/antigravity-2/build_antigravity.py`
- `adapters/antigravity-2/gates/mainframe_hook.py`
- `tools/test_build_antigravity.py`
- `tools/test_antigravity_hook.py`
- <https://antigravity.google/docs/plugins>
- <https://antigravity.google/docs/hooks>
