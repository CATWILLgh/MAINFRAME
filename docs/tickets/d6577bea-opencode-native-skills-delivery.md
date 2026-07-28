---
id: d6577bea
title: OpenCode skills delivery rides the ~/.claude compat scan — probe a native install target
status: closed
priority: low
component: opencode-layer
discovered: 2026-07-09
discovered-from: ["#5fae0bfa"]
tags: ["opencode", "skills", "delivery", "research"]
---

# d6577bea: OpenCode skills delivery rides the ~/.claude compat scan — probe a native install target

## What was observed

`opencode debug skill` (1.17.15, this machine): all 18 hub skills resolve via
`/Users/user/.claude/skills/mainframe` — OpenCode's built-in Claude-Code
compatibility scan of `~/.claude`. `~/.config/opencode/` contains no skills
directory; `install.sh --opencode` links agents, plugins and AGENTS.md but
not skills. User direction (2026-07-09): instruction prose must not carry
tool-foreign paths — delivery is the installer's concern (the AGENTS.md
runtime note now says load-by-name only).

## Why it is a problem

The OpenCode skills supply hangs off another tool's dotdir and off OpenCode's
compat behavior (plural-`skills/` glob was a recent fix, issue #6177 — older
or future versions may scan differently). If either side changes, skills
silently vanish from OpenCode sessions.

## Why it is not a duplicate

[#5fae0bfa](5fae0bfa-opencode-tuned-agents-md-variant.md) is about skill/agent
PROSE truth on OpenCode; this is about the DELIVERY path of skill files.

## What probably needs to be done

1. Verify against OpenCode docs + `opencode debug skill` empirically: does it
   scan a native global dir (`~/.config/opencode/skills/` or `skill/`)? Which
   wins when the same skill name exists in both native and compat locations
   (dedup? shadowing?).
2. If a native dir exists: extend `install.sh --opencode` to link
   `core/skills` (or `plugin-dist/skills`) there, mirroring agents/plugins;
   verify no duplicate-skill listing results from double discovery.
3. If none exists: record the compat-scan dependency as accepted, with the
   version caveat, in `docs/` and the compat memory.

## Acceptance criteria

- A cited answer (docs quote or debug transcript) on native skill discovery.
- Either the install link exists and `opencode debug skill` shows skills
  resolving from the native dir without duplicates, or the dependency is
  documented as accepted.

## Sources

- `opencode debug skill` probe 2026-07-09 (18 × `~/.claude/skills/mainframe`)
- `adapters/opencode/instructions/90-runtime-opencode.md` (load-by-name note)

## Resolution (2026-07-09)

**Implementer:** autonomous session (Fable 5)
**Commits:** `a9150565fbfee2d115f6949e584fecf18526ff0c`
(OpenCode instruction correction),
`871bd274f22bbc88c8834a829c87b2bc236b51ae` (native skill links)
**Summary of facts established:**
- Docs (opencode.ai/docs/skills): six fixed scan locations — project
  `.opencode/skills` / `.claude/skills` / `.agents/skills` + global
  `~/.config/opencode/skills` / `~/.claude/skills` / `~/.agents/skills`;
  no config key for custom paths; precedence UNDOCUMENTED.
- Empirical (1.17.15, this machine): probe skills in BOTH
  `~/.config/opencode/skills/` and singular `skill/` resolve; on a duplicate
  name the listing stays SINGLE and the `~/.claude` compat copy wins (probe
  marker absent, hub path shown) — dedup by name, no doubles.
- Therefore native links are harmless insurance: same content either way
  (both are symlinks to `plugin-dist/skills`), seamless takeover if the
  compat scan ever changes.
**Implementation:** `install.sh --opencode` links `plugin-dist/skills`
contents into `~/.config/opencode/skills/` (canonical documented plural dir)
+ stale cleanup + uninstall; dry-run verified.
**Claims to verify on audit:**
- `./install.sh --opencode --dry-run` lists the "would link hub skills" step.
- After a user-run install: `opencode debug skill` still lists each hub skill
  exactly once.
- Probe transcripts: scratchpad `skills-dump2.txt` / `skills-dump3.txt`
  (session-local); probes cleaned from `~/.config/opencode`.
