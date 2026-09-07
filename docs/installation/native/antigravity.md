# Antigravity orientation

Last reviewed: 2026-09-07.

Antigravity CLI and IDE surfaces can evolve independently. Recheck the installed
versions, customization roots, plugin support, browser availability, and current
official documentation before adapting.

## Official sources

- [Plugins and skills](https://antigravity.google/docs/cli/plugins/)
- [Hooks](https://antigravity.google/docs/hooks)
- [Rules](https://antigravity.google/docs/rules-workflows)
- [Workflows to skills migration](https://antigravity.google/docs/migration/workflows-to-skills)

## Current orientation

| MAINFRAME concern | Native direction to verify |
| --- | --- |
| Global instruction | Global Rules owner in the active CLI or IDE surface |
| Skills | Native Agent Skills, either directly or inside an installed product-specific plugin |
| Agents | Native agent/subagent templates when supported by the installed surface |
| Commands | Prefer a current explicitly invoked skill representation; workflows are a migration concern, not a default new target |
| Hooks | Native `hooks.json`, directly or in a plugin, with documented pre/post/invocation/stop events |
| Frontend browser proof | Native Antigravity browser when available and adequate for real user interaction and console evidence |

A generated Antigravity plugin may be a clean installed container for native
skills, agents, hooks, MCP, and rules. It remains target-specific adapter output,
not a directory to commit as canonical MAINFRAME source. Keep one stable plugin
identity if this packaging is chosen.

## Adaptation decisions

1. Separate CLI and IDE customization roots and versions before deciding whether
   one installation serves both.
2. Choose direct native components or one generated plugin based on current
   product ownership and precedence. Do not install both representations.
3. Translate explicit MAINFRAME commands to the current user-invocable mechanism
   without converting them to automatically selected skills. Record any
   inability to prevent autonomous invocation.
4. Map hooks only to documented events with equivalent timing and effect. Verify
   collaboration events separately when subagents must receive the rule.
5. Keep plugin manifests, schemas, event names, and absolute paths only in the
   globally installed adapter copy.
6. Use the native browser for `mainframe-frontend` only after a harmless probe
   proves it can operate the real target and expose the required evidence.

## Useful probes

- List active plugins, skills, agents, and rules in both relevant surfaces.
- Validate a generated plugin with the current schema and native tooling.
- Invoke one command-like skill only through the user path and observe whether
  the model can also select it autonomously.
- Trigger each hook using the documented synthetic or harmless action path.
- Perform one visible browser interaction, navigation check, and console check.

Do not restore a deprecated workflow simply because an old adapter used one.
Do not claim a CLI plugin proves IDE discovery unless both surfaces expose the
same effective component.
