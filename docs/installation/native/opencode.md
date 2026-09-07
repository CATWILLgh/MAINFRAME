# OpenCode orientation

Last reviewed: 2026-09-07.

This page is a dated map. Recheck the installed OpenCode version, TUI/CLI/Desktop
surfaces, configuration precedence, and official documentation before writing.

## Official sources

- [Configuration](https://opencode.ai/docs/config)
- [Rules](https://opencode.ai/docs/rules)
- [Agent Skills](https://opencode.ai/docs/skills)
- [Agents](https://opencode.ai/docs/agents)
- [Commands](https://opencode.ai/docs/commands)
- [Permissions](https://opencode.ai/docs/permissions)
- [Plugins](https://opencode.ai/docs/plugins)

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | OpenCode's effective global rules/instructions layer, preserving config precedence |
| Skills | Native global Agent Skills directory; OpenCode also discovers compatible Claude and Agent Skills locations, so choose one owner and prevent duplicates |
| Agents | Global agent definitions or configuration with mode, permissions, visibility, and prompt |
| Commands | Global command Markdown or config entries, with the file/config identity shown as a slash command |
| Hooks | Plugin events or another documented extension point only if it reproduces timing, payload, blocking/advisory effect, and concurrency safely |
| Settings and permissions | Effective global config and per-agent permission rules |

OpenCode documents several compatible skill roots. That is discovery
compatibility, not a reason to install the same skill three times. Select the
native owner for this product, reconcile by skill identity, and inspect the
effective catalog for collisions.

## Adaptation decisions

1. Determine which global config file and directories the installed binary
   actually uses, including environment overrides and config merge order.
2. Select one global skill owner. Preserve unrelated compatible-path skills and
   remove only positively identified obsolete MAINFRAME duplicates after proof.
3. Build native agent definitions from role matrices. Preserve primary versus
   subagent mode and map allowed/denied capabilities through current permission
   syntax.
4. Adapt commands as no-argument global command identities. Do not set a model,
   agent, or subtask option unless the canonical command requires that behavior.
5. Treat plugin code as an installed adapter layer, not canonical product
   source. Prove that its event can block before a protected effect or deliver a
   bounded advisory before marking a hook installed.
6. Test every interface actually used by the user; a TUI command appearing does
   not by itself prove a separate desktop wrapper loaded the same config.

## Useful probes

- Inspect the effective config and native help without dumping provider secrets.
- Use the skill and agent listings or UI and invoke one harmless identity.
- Type each installed command name and verify the correct template and current
  project root.
- Trigger a plugin hook with a synthetic action and verify clean silence,
  finding behavior, and operational failure behavior.
- Re-run discovery after a restart or documented reload and confirm no duplicate
  compatible-path skill remains.

If OpenCode cannot provide the exact pre-action or continuation event required
by a hook, mark that hook unsupported. Do not emulate a guard with an agent
prompt or a repository-wide scan.
