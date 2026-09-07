# Codex orientation

Last reviewed: 2026-09-07.

This page is a starting map, not a frozen adapter. Recheck the current Codex
version, effective home/configuration layers, Desktop and CLI behavior, and all
linked official documentation before writing.

## Official sources

- [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Skills](https://learn.chatgpt.com/docs/build-skills)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Hooks](https://learn.chatgpt.com/docs/hooks)
- [Custom prompts](https://learn.chatgpt.com/docs/custom-prompts)

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | Codex's global `AGENTS.md` or override layer, preserving user-owned content and precedence |
| Skills | Native personal Agent Skills discovery and optional skill configuration; do not assume an older `~/.codex/skills` layout |
| Agents | Custom agent configuration with per-role instructions, model defaults, sandbox, tools, and skill attachment where supported |
| Commands | Explicit user invocation is required; current custom prompts are documented as deprecated, so first determine whether a user-only skill or another current native command surface preserves the command contract |
| Hooks | `hooks.json` or inline hook configuration at an effective native config layer, with a thin wrapper around canonical detectors |
| Settings and permissions | Effective Codex configuration and sandbox/approval layers, preserving managed and user precedence |

Codex currently documents matching hooks as concurrent. Do not use registration
order as a safety dependency. Each MAINFRAME wrapper must be independently
correct, bounded, and safe when several hooks, sessions, or subagents run at
once.

## Adaptation decisions

1. Identify whether Desktop and CLI use the same executable version,
   configuration home, skill catalog, agent registry, and hook dispatcher.
2. Resolve the effective global instruction chain before merging the
   MAINFRAME-owned section. Root [AGENTS.md](../../../AGENTS.md) in this
   repository remains project guidance, not the global payload source.
3. Install skills in the currently documented personal skill location and prove
   both catalog visibility and body loading.
4. Generate native custom-agent files or configuration from each role matrix.
   Keep the user's model default unless a role requirement proves otherwise.
5. For commands, prefer a current mechanism that keeps content out of routine
   context and is only user-invocable. Record a degradation if Codex cannot
   represent both properties.
6. Bind hooks only to documented events whose timing and output contract match
   the canonical rule. Verify subagent delivery separately where relevant.

## Useful probes

- Inspect the actual CLI version and resolved executable without changing it.
- Use the native skills surface or listing, then invoke one harmless installed
  skill and confirm a referenced file loads.
- Start a fresh session to prove instruction changes.
- List or invoke one custom agent in an isolated scope and test its permission
  boundary.
- Trigger each hook with a harmless synthetic action; test Desktop and CLI
  separately if their dispatch path differs.

Do not report the desktop app as verified because the CLI parsed the same file.
Do not install deprecated prompt copies alongside a working current command
representation merely for compatibility.
