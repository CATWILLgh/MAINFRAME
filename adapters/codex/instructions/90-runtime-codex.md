## Runtime notes (Codex)

- Skills are NOT preloaded into context. Invoke a method explicitly by name with `$<name>`; Codex loads that skill body on demand.
- Sub-agent dispatch is explicit. Do not expect an agent description to auto-match a task; choose and dispatch a sub-agent deliberately with a self-contained prompt.
- There is no `advisor` tool. Use a fresh reviewer sub-agent for review checkpoints and give it the decision or finished artifact, alternatives, assumptions, and relevant paths.
- Permission and safety policy is loaded from `~/.codex/rules/*.rules`. The hub owns `mainframe.rules`; it coexists with the user's `default.rules`.
