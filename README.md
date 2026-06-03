<p align="center">
  <img src="assets/banner.png" alt="MAINFRAME" width="100%">
</p>

# MAINFRAME

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-v2.1%2B-blueviolet)](https://code.claude.com)
[![Status](https://img.shields.io/badge/status-personal--use-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](#platforms)
[![Tuned for](https://img.shields.io/badge/tuned%20for-Opus%204.7%2B-blueviolet.svg)](#tested-configuration)
[![Last commit](https://img.shields.io/github/last-commit/CATWILLgh/MAINFRAME?label=last%20commit)](https://github.com/CATWILLgh/MAINFRAME/commits)
[![Skills](https://img.shields.io/github/directory-file-count/CATWILLgh/MAINFRAME/plugin-dist/skills?type=dir&label=skills&color=blue)](plugin-dist/skills)
[![Agents](https://img.shields.io/github/directory-file-count/CATWILLgh/MAINFRAME/plugin-dist/agents?type=file&extension=md&label=agents&color=blue)](plugin-dist/agents)
[![Hooks](https://img.shields.io/github/directory-file-count/CATWILLgh/MAINFRAME/plugin-dist/hooks/scripts?type=file&extension=py&label=hooks&color=blue)](plugin-dist/hooks/scripts)
[![Style](https://img.shields.io/badge/principles-agnostic%20%7C%20evidence--based%20%7C%20English-blue.svg)](#principles)

<img src="assets/badge.png" align="right" width="80"> Maintained by [@CATWILLgh](https://github.com/CATWILLgh)

A baseline of operating rules, focused sub-agents, and small automatic checks I want to apply in **every** Claude Code session on my machine. Set up once — every project, every session, inherits the same discipline.

> **Personal-use.** No support, no compatibility guarantees, no backwards-compatibility promises. Forks are welcome under MIT, but this hub is shaped to one engineer's workflow.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Why this exists

Working with Claude Code (or any AI coding agent) on multiple projects, you keep running into the same friction:

- **Same baseline, every time.** You re-deploy the same useful sub-agents, the same operating rules, the same little safety checks for every new project. Manually. Forever.
- **Project-level config doesn't scale.** Putting it all into the project's own `CLAUDE.md` works — until that file grows. Then attention scatters, the well-known **lost-in-the-middle** problem kicks in, and important rules quietly stop being followed mid-session.
- **The agent itself bloats its own config.** Left to its habits, Claude keeps appending new instructions to `CLAUDE.md`. The file grows, focus thins, the rules crumble. And so it grows, slowly, until you notice the discipline you started with is gone.

This repo is my attempt to do that baseline layer **separately** from any specific project, with deliberate size limits and small reminders so things don't drift:

- Strict file-size budgets on skills, agents, hooks. A file gets too big — a hook nudges me.
- Skills and agents stay granular and narrowly focused — at any moment, only the most relevant context is loaded, not a soup of "a little bit of everything".
- Constantly iterating: try a new approach, see what stabilizes Claude's behavior, keep what works, drop what doesn't.
- Every decision cross-checked against authoritative sources (Anthropic docs, RFCs, well-known engineering material) — not "feels right".

**Honest disclaimer.** I'm not claiming this hub closes every pain. Some friction with AI agents is just current-generation model limits — the best a hub can do is smooth them, not fix them. What I am aiming for: a higher minimum quality of output code by default. On long-running development that pays back many times over — problems caught and prevented up front instead of bugs to chase later, by you or by the agent.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Where this comes from

This isn't a weekend project or a copied template. It's distilled from thousands of hours of working with AI coding agents, day after day — what consistently helped, what quietly broke, what was worth keeping. Every rule here earned its place by surviving real use.

Three things shape it:

- **Hard-won experience.** The rules come from patterns I hit over and over on real projects — not from theory.
- **Authoritative sources.** I don't ship a rule on a hunch. Each non-trivial decision is checked against primary sources — Anthropic's own docs, RFCs, established engineering material — and validated with a small experiment where I can.
- **Constant feedback.** I work on this almost every day, together with the agent. When something underperforms in real use, it gets refined or dropped. The hub is never "finished" — it's continuously corrected against what actually happens.

And here's the part that's easy to miss. It looks like just a folder of Markdown files — some skills, a few agents. It isn't. Steering a language model reliably, across many projects and long autonomous runs, is one of the genuinely hard parts of working with agentic systems. The model's inference — how it generates each step — is a kind of *ordered chaos*: powerful, but hard to keep pointed in the right direction at scale. This hub is my standing attempt to put just enough structure around that chaos to make the output dependable, without strangling what the model is good at.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## What you actually get

In plain words — what each piece is for:

- **Umbrella `CLAUDE.md`** — a tight set of working rules Claude follows in every project on your machine. Partnership-mode, honest pushback when I'm wrong, no flattery, source-checking before non-trivial decisions, atomic commits, no leftover `TODO`/`FIXME` markers, and so on. About 200 lines, intentionally short to stay in focus.
- **Skills** — small focused playbooks Claude pulls when they're relevant. Things like "audit this code carefully", "format this commit message in Conventional Commits style", "scan this diff for forgotten secrets" — instead of one giant document trying to cover everything.
- **Agents (sub-agents)** — pre-configured specialists with their own model and effort level wired in. Backend engineers for Python and Node.js, a frontend engineer for React, a devops engineer for deploys and infra, a decision-reviewer for high-stakes design calls, and a web-search agent for authoritative source-checking. You don't have to remember which model to pick for what — the right one is already attached.
- **Hooks** — small automatic checks that run on tool events. Catch leftover `TODO`/`FIXME` markers before commit. Warn on risky bash patterns. Scan diffs for security issues with `ruff`/`semgrep`/`osv-scanner`. Things that fire without you having to remember to fire them.
- **Rules** — small path-scoped guidance files that load on demand when Claude reads a matching path. Doesn't bloat the global context.
- **Permissions** — three-tier model (deny / ask / allow) that's strict by default. Some things must never run; some need confirmation; the rest run quietly with logging.

End result the hub aims for: **the same baseline of quality and discipline applied to every project on your machine — without re-configuring Claude each time or babysitting it during a session.** When the baseline is high, day-to-day output is more predictable and bug rate drops.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Architecture

```mermaid
graph LR
    subgraph repo["MAINFRAME repo (this)"]
      P[plugin-dist/<br/>skills + agents + hooks + commands]
      E[export/<br/>CLAUDE.md + settings.json + rules + secret helper]
    end

    P -->|one symlink<br/>~/.claude/skills/mainframe/| home[~/.claude/]
    E -->|per-item symlinks| home
    home -->|Claude auto-loads<br/>as 'mainframe' plugin| any[Any project<br/>on the machine]
```

The hub ships in two channels:

- **A plugin** (`plugin-dist/`) carries skills, agents, hooks, and commands. After install, Claude Code auto-loads it as the `mainframe` plugin via the skills-dir mechanism, and everything inside becomes available with the `mainframe:` namespace prefix (e.g. `/mainframe:code-audit`, `subagent_type: "mainframe:python-backend-engineer"`). That namespace is the visible mark that something is coming from this hub, not from your local project setup or another plugin.
- **Single-file and per-item symlinks** (`export/`) carry the umbrella `CLAUDE.md`, the permission `settings.json`, path-scoped `rules/`, and a small credentials helper — pieces the plugin format does not currently support.

See [`docs/layers/`](docs/layers/) for full per-layer specifications.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Requirements

**Required:**

- **Claude Code v2.1+** — the host (CLI or IDE extension).
- **git** — to clone the repo, and for the hooks that diff your working tree.
- **Bash 3.2+** — to run `install.sh` (macOS system Bash is fine; no GNU-only extensions used).
- **Python 3** — the validators and most hooks are stdlib Python 3. Without it they silently no-op (the installer warns; it does not fail).

**Recommended — each unlocks a group of checks; anything missing just stays silent, and `install.sh` prints an OS-specific install hint:**

- **Node.js / npm** — the React and Node.js agents, the shadcn CLI (`npx`), the frontend recon script, and the JS hooks (`oxlint`, `dependency-cruiser`, `knip`).
- **uv or pipx** — installs the Python tooling the hooks call: `ruff`, `semgrep`, `pip-audit`.
- **osv-scanner** — the dependency-vulnerability hook (`install.sh` can fetch the binary for you).

Nothing here hard-fails a session: a tool that isn't installed disables only its own hook. Run `./install.sh --dry-run` to preview everything and see exactly what's missing.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Install

```bash
git clone https://github.com/CATWILLgh/MAINFRAME ~/Documents/projects/MAINFRAME
cd ~/Documents/projects/MAINFRAME
./install.sh
```

```mermaid
graph LR
    A[git clone] --> B[./install.sh]
    B --> C[plugin-dist/ →<br/>~/.claude/skills/mainframe/]
    B --> D[export/CLAUDE.md & settings.json<br/>→ ~/.claude/ symlinks]
    B --> E[export/rules/* →<br/>~/.claude/rules/ per-item]
    C --> F[Claude auto-loads<br/>'mainframe' plugin]
    D --> G[Umbrella + permissions<br/>active in every session]
    E --> G
    F --> G
```

What `install.sh` does:

- **One symlink for the plugin** — `plugin-dist/` becomes `~/.claude/skills/mainframe/`. Claude Code auto-loads it and prefixes everything inside with the `mainframe:` namespace.
- **Single-file symlinks** for the umbrella `CLAUDE.md` and the permission `settings.json` (the plugin format does not provide an equivalent for these).
- **Per-item symlinks** for `export/rules/*` into `~/.claude/rules/`, so the hub composes with any rules you already have without replacing the whole directory.
- **Credentials helper** — links `export/scripts/secret` into `~/.local/bin/` and seeds `~/.config/credentials/` + `~/.claude/credentials-index.md` from the template.
- **Stale-symlink cleanup** — on first run after upgrading from the older per-item layout, removes leftover hub symlinks under `~/.claude/{skills,agents,hooks}/`.
- **Backs up** any pre-existing real file before replacing it with a symlink.
- **Idempotent** — re-running is a no-op when state matches.

Options:

```
./install.sh              # install (with backups)
./install.sh --dry-run    # preview, no changes
./install.sh --uninstall  # remove managed symlinks
./install.sh --help
```

To temporarily disable the plugin without uninstalling, use `claude plugin disable mainframe` (and `claude plugin enable mainframe` to re-enable).

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Update

```bash
cd ~/Documents/projects/MAINFRAME
git pull
```

That's it. Symlinks point to files in this repo — the next Claude Code session sees the latest. Re-run `install.sh` **only** if a new top-level directory appeared under `export/`.

```mermaid
graph LR
    A[git pull] --> B[Files updated<br/>in repo]
    B --> C[Symlinks already<br/>point to repo]
    C --> D[Next Claude session:<br/>latest active]
```

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Tested configuration

What I have actually verified this hub on:

- **Claude Code CLI** — the primary surface I use daily.
- **Claude Code IDE extension** — also in active use.
- **Main thread model**: Claude **Opus 4.7+** at `high` or `xhigh` effort. This is what I run every day and what all the discipline is tuned against.
- **Sub-agents** — each one calibrated separately via a small empirical tournament so the right model + effort sits inside the agent file itself. You don't have to think about it at call time.

Other model / effort combinations may work but I haven't verified them. When an agent's prompt body changes in a meaningful way, I re-run its tournament.

**Trying the hub on other models or effort levels is very welcome** — Sonnet, Haiku, lower or higher effort, different IDEs. Share what you observe (open an issue or a PR with notes); empirical results on configurations I don't run daily are exactly the kind of feedback the hub gets better from.

**OpenAI Codex** support is in the future-list, not in scope yet.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Platforms

- **macOS** — primary, tested daily.
- **Linux** — should work; `install.sh` is plain Bash 3.2+ compatible, no macOS-specific paths.
- **Windows** — not supported yet, no timeline for it.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Directory map

```
MAINFRAME/
├── README.md, LICENSE, CONTRIBUTING.md   # project meta
├── install.sh                            # installer (creates the symlinks into ~/.claude/)
├── assets/                               # README images (banner, divider, badge)
│
├── plugin-dist/                          # the plugin — auto-loads as 'mainframe' after install
│   ├── .claude-plugin/plugin.json        # plugin manifest (name, version, license)
│   ├── skills/                           # 17 skills, one folder per skill
│   ├── agents/                           # 6 file-based sub-agents (Python, Node.js, React, devops, decision-reviewer, web-search)
│   ├── commands/                         # slash commands (currently empty)
│   └── hooks/
│       ├── hooks.json                    # which hook fires on which event
│       ├── scripts/                      # 19 Python scripts (security scans, marker discipline, ...)
│       └── rules/                        # Semgrep YAML rules
│
├── export/                               # what the plugin format does NOT carry
│   ├── CLAUDE.md                         # umbrella operating rules (partnership, evidence, honesty, ...)
│   ├── settings.json                     # permissions (allow/ask/deny tiers)
│   ├── rules/                            # path-scoped guidance (currently empty, future-proof)
│   ├── scripts/secret                    # credentials helper script
│   └── templates/credentials-index.md    # starter template for the credentials index
│
├── tools/                                # Python validators (used by hooks; runnable manually)
│   ├── validate-claude-md.py             # umbrella spec + project-agnosticism check
│   ├── validate-skill.py                 # skill format + size limits
│   └── agnostic-blacklist.txt.example    # copy to agnostic-blacklist.txt and add your own project names
│
└── docs/
    └── layers/                           # architecture spec per layer (skills, agents, hooks, rules, ...)
```

Anything you do not see here lives outside the repo by design — internal ADRs, working notes, the maintainer's inbox of unprocessed candidates, and per-machine memory are all gitignored. The published artifact is the hub itself, not the maintainer's working files.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Layer architecture

Each artifact type has its own layer with explicit contract: where it lives, what frontmatter it carries, what limits apply, when it activates. New artifacts go through a decision tree to land in the correct layer.

```mermaid
graph TD
    Start[New hub artifact<br/>needs a home] --> Q1{Triggers on<br/>file path?}
    Q1 -->|yes| Rules[rules/<br/>paths: frontmatter]
    Q1 -->|no| Q2{User invokes<br/>by slash?}
    Q2 -->|yes| Commands[commands/<br/>or skills user-invocable]
    Q2 -->|no| Q3{Domain<br/>playbook?}
    Q3 -->|yes| Skills[skills/]
    Q3 -->|no| Q4{Tool event<br/>trigger?}
    Q4 -->|yes| Hooks[hooks/]
    Q4 -->|no| Q5{Isolated<br/>subagent?}
    Q5 -->|yes| Agents[agents/]
    Q5 -->|no| CLAUDE[Add to umbrella<br/>CLAUDE.md]
```

| Layer | Spec |
|---|---|
| Umbrella `CLAUDE.md` | [`docs/layers/claude-md.md`](docs/layers/claude-md.md) |
| Skills | [`docs/layers/skills.md`](docs/layers/skills.md) |
| Agents | [`docs/layers/agents.md`](docs/layers/agents.md) |
| Hooks | [`docs/layers/hooks.md`](docs/layers/hooks.md) |
| Rules | [`docs/layers/rules.md`](docs/layers/rules.md) |
| Commands | [`docs/layers/commands.md`](docs/layers/commands.md) |
| Permissions | [`docs/layers/permissions.md`](docs/layers/permissions.md) |
| Settings | [`docs/layers/settings.md`](docs/layers/settings.md) |
| Output styles | [`docs/layers/output-styles.md`](docs/layers/output-styles.md) |
| Decision tree | [`docs/layers/decision-tree.md`](docs/layers/decision-tree.md) |

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Principles

Every artifact shipped by this hub (whether in `plugin-dist/` or `export/`) holds these:

1. **Project-agnostic** — no hardcoded project names, stacks, paths, or domains.
2. **Evidence-based** — new rules need real experience, an authoritative source, or a measured experiment. Not "feels right".
3. **English in artifacts** — skills, agents, commands, hooks all in English (LLM adherence).
4. **Single source of truth** — each artifact exists in exactly one location in the repo.
5. **Sub-agent economy** — pick the right model per task (Haiku for trivial, Sonnet for most research, Opus only for genuine reasoning needs).

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## Contributing

This is a personal hub but friends, acquaintances, and curious strangers are welcome to fork, adapt, and share what works. The repo gets better when more people poke at it from different angles — new approaches, sharper rules, things I haven't tried.

See [CONTRIBUTING.md](CONTRIBUTING.md) for fork conventions, principles, validators, and commit format.

<p align="center">
  <img src="assets/divider.png" alt="" width="100%">
</p>

## License

[MIT](LICENSE) — use, fork, modify freely, no warranty.
