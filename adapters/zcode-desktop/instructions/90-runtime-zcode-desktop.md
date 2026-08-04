
## Runtime notes (ZCode Desktop)

- User-wide instructions live in `~/.zcode/AGENTS.md`; ZCode appends the current workspace `AGENTS.md` after them and treats the workspace file as the primary project source.
- Reusable public methods live in `~/.zcode/skills/` and may be invoked with `$<name>`. Private agent methods are embedded into the intended subagent and never published to a skill discovery root.
- Custom subagents are a beta ZCode surface. Their native files contain only directly verified fields and tool names. ZCode decides foreground or background execution when dispatching; the neutral `background` preference is not emitted as unsupported file metadata.
- When the user explicitly asks for a long-running goal, use ZCode's native `/goal` surface to keep continuation and recovery visible. `task-workflow` still owns engineering execution, and completion still requires MAINFRAME verification. Do not create a goal for routine work or infer one from an ordinary multi-step request.
- The adapter does not enable ZCode memory, browser control, remote execution, plugins, MCP servers, or automations implicitly. Those capabilities keep their own explicit activation boundaries.
