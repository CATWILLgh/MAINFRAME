## Runtime notes (OpenCode)

- Skills are NOT preloaded here. Load a method before relying on it: the `skill` tool (`skill({ name: "..." })`) pulls a hub skill's text into context; hub skills resolve from `~/.claude/skills/mainframe/skills/`.
- There is no `advisor` tool. For review checkpoints, dispatch the `decision-reviewer` agent with a self-contained prompt (it sees only what you pass it) — before locking in a high-stakes approach, and again before declaring a large task done.
- Permission `ask` degrades to allow in auto mode: treat permission gates as advisory and the Destructive-actions section above as your own discipline, not something the runtime enforces. The hub's `mainframe-gates` plugin hard-blocks the two worst cases (secret commits, deletes outside the working tree) and appends advisory notes after risky edits — read those notes, they are findings.
- There is no structured-question tool: when only the user can decide, ask in plain chat text; unattended, record the assumption and proceed.
