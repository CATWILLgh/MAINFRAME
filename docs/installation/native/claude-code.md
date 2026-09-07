# Claude Code orientation

Last reviewed: 2026-09-07.

This page is a dated map. Verify the installed Claude Code version, effective
setting sources, project and user precedence, and current official documentation
before adapting.

## Official sources

- [Memory and CLAUDE.md](https://code.claude.com/docs/en/memory)
- [Skills and slash commands](https://code.claude.com/docs/en/slash-commands)
- [Subagents](https://code.claude.com/docs/en/sub-agents)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Permissions](https://code.claude.com/docs/en/permissions)
- [Settings](https://code.claude.com/docs/en/settings)

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | User-level Claude memory/instruction owner; preserve imports, managed sources, and user text |
| Repository bootstrap | Root `CLAUDE.md` can import `AGENTS.md`; MAINFRAME uses that thin bridge rather than duplicating project guidance |
| Skills and commands | Native skills; use user-invocation controls for commands and ordinary proactive descriptions for reusable skills |
| Agents | User subagent definitions with native frontmatter, tools, permissions, skills, and reload behavior |
| Hooks | User settings or another documented effective hook source, with one stable MAINFRAME-owned registration per component |
| Permissions | Effective user/managed permission layers; plugin-scoped agent restrictions may differ from user agents |

Claude Code currently documents `disable-model-invocation: true` for a skill
that only the user may invoke. Use that for MAINFRAME commands when the installed
version preserves the contract. Do not apply it to proactive MAINFRAME skills.

## Adaptation decisions

1. Resolve which setting sources are active and whether a managed layer limits
   user hooks, agents, skills, or permissions.
2. Merge the global instruction into the actual user owner. Do not globally
   install this repository's `CLAUDE.md`; it is only the repository bridge.
3. Adapt skills and commands as separate native identities even if both use the
   skill file format. Commands remain explicit-only and no-argument.
4. Put role metadata in installed subagent frontmatter, attach required skills,
   and test any tool or permission boundary. Do not assume plugin agents support
   every user-agent field.
5. Merge hook settings by stable MAINFRAME identity. Preserve unrelated hook
   arrays and effective precedence.
6. Verify live reload behavior for existing directories and restart when the
   installed version requires it, especially after creating a scope's first
   agent directory.

## Useful probes

- Use native diagnostics or listing to locate duplicate agents and effective
  configuration.
- Invoke a MAINFRAME command explicitly and verify its description/body was not
  offered for autonomous use.
- Route a harmless task to one installed subagent and verify its attached skill
  and permissions.
- Exercise a clean and finding hook payload through the actual user hook layer.
- Start a fresh project session and confirm `CLAUDE.md` resolves the root import.

Do not add both a copied `CLAUDE.md` body and an `@AGENTS.md` import. Do not treat
an allowed skill invocation as proof that a subagent's tool restriction works.
