
## Runtime notes (ZCode Desktop)

- User-wide instructions live in `~/.zcode/AGENTS.md`; ZCode appends the current workspace `AGENTS.md` after them and treats the workspace file as the primary project source.
- Reusable public methods live in `~/.zcode/skills/` and may be invoked with `$<name>`. Private agent methods are embedded into the intended subagent and never published to a skill discovery root.
- Custom subagents are a beta ZCode surface. Their native files contain only directly verified fields and tool names. ZCode decides foreground or background execution when dispatching; the neutral `background` preference is not emitted as unsupported file metadata.
- The adapter does not enable ZCode memory, browser control, remote execution, plugins, MCP servers, or automations implicitly. Those capabilities keep their own explicit activation boundaries.
