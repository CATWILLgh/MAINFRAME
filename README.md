# MAINFRAME

A personal hub of global Claude Code customizations — `CLAUDE.md` umbrella, skills, agents, hooks, rules — that take effect across every project on the machine.

> **Status: personal-use.** No support, no compatibility guarantees, no backwards-compatibility promises.
> Forks and adaptations are welcome under MIT, but this hub is shaped to one engineer's workflow.

## Install

```bash
git clone https://github.com/<your-fork>/MAINFRAME ~/Documents/projects/MAINFRAME
cd ~/Documents/projects/MAINFRAME
./install.sh
```

`install.sh` is idempotent — it creates per-item symlinks from this repo's `export/` into `~/.claude/`, backs up anything pre-existing, and runs a drift cleanup on subsequent runs. See `./install.sh --help` for options (`--dry-run`, `--uninstall`).

## Update

```bash
cd ~/Documents/projects/MAINFRAME
git pull
```

Symlinks point to files in this repo — `git pull` is enough, the next Claude Code session sees the latest. Re-run `install.sh` only if the layer structure changes (new top-level directory under `export/`).

## What's inside

| Path | Content |
|------|---------|
| `export/CLAUDE.md` | Umbrella operating instructions loaded into every Claude Code session |
| `export/settings.json` | Permission rules (allow/ask/deny) and hook registration |
| `export/skills/` | Claude Code skills — domain-specific playbooks and capabilities |
| `export/agents/` | File-based subagents with narrow tool allowlists |
| `export/hooks/` | Pre/post-tool-use scripts (Python) for live validation and safety |
| `export/rules/` | Path-scoped rule files loaded on-demand via `paths:` frontmatter |
| `export/commands/` | Slash commands |
| `export/output-styles/` | Output style overrides |
| `tools/` | Validators for `CLAUDE.md` and `SKILL.md` (Python, used by hooks) |
| `docs/layers/` | Architecture specifications for each layer of the hub |

## Layer architecture

Each artifact type has its own contract. The full specs live in [`docs/layers/`](docs/layers/):

- `claude-md.md` — Anthropic `CLAUDE.md` spec + agnosticism principle
- `skills.md` — skill format, token/line limits, frontmatter completeness
- (additional layer specs as they stabilize)

## License

[MIT](LICENSE) — use, fork, modify freely, no warranty.
