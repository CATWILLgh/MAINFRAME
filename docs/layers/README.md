# MAINFRAME Hub Layers

> Canonical list of `export/` layers and a navigator to their specifications.
> Goal: a shared understanding of "what exactly we have, what each layer is responsible for, how it works, and how to update it" — no half-intuitive moves.

> **Status:** active reference. Created 2026-05-28. Updated as new empirical findings, new ADRs, and new authoritative sources emerge.

---

## What counts as a "layer"

A layer = a type of artifact in `export/` that is delivered to `~/.claude/` via symlink (`install.sh`) and applies across **all** of the user's projects without any per-project edits.

**Not layers:**
- `docs/layers/` — layer specifications (what you are reading now).
- `tools/` — scripts owned by the hub (validators).

## Canonical layer list

| # | Layer | Where it lives | What is delivered to `~/.claude/` | Spec |
|---|---|---|---|---|
| 1 | **CLAUDE.md** (operating instructions) | `export/CLAUDE.md` | `~/.claude/CLAUDE.md` (file symlink) | [claude-md.md](claude-md.md) |
| 2 | **Rules** (path-scoped) *(planned, empty)* | `export/rules/<name>.md` | `~/.claude/rules/<name>.md` (symlinks) | [rules.md](rules.md) |
| 3 | **Skills** | `export/skills/<name>/` | `~/.claude/skills/<name>/` (directory symlink) | [skills.md](skills.md) |
| 4 | **Hooks** | `export/hooks/*.py` + `export/settings.json` `hooks.*` | `~/.claude/hooks/*.py` (symlinks) + registration in settings | [hooks.md](hooks.md) |
| 5 | **Permissions** | `export/settings.json` `permissions.{allow,deny,ask}` | part of `~/.claude/settings.json` (whole-file symlink) | [permissions.md](permissions.md) |
| 6 | **Settings** (other fields) | `export/settings.json` (everything except permissions/hooks) | part of `~/.claude/settings.json` | [settings.md](settings.md) |
| 7 | **Agents** *(planned, empty)* | `export/agents/<name>.md` | `~/.claude/agents/<name>.md` (symlinks) | [agents.md](agents.md) |
| 8 | **Commands** *(planned, empty)* | `export/commands/<name>.md` | `~/.claude/commands/<name>.md` (symlinks) | [commands.md](commands.md) |
| 9 | **Output styles** *(planned, empty)* | `export/output-styles/<name>.md` | `~/.claude/output-styles/<name>.md` (symlinks) | [output-styles.md](output-styles.md) |

**Notes:**
- (4), (5), and (6) technically live in a single file (`settings.json`), but they are **separate layers** — they have different syntax rules, different eval semantics, different failure modes, and different sources of truth. Their specs are kept separate.
- (2), (7), (8), (9) are reserved in advance; (2) Rules was introduced on 2026-05-29 after empirical verification of paths-activation; no concrete files exist in `export/rules/` yet — they will be added as path-scoped guidance is identified.
- All symlinks are created by `install.sh` — covering all 8 layers since 2026-05-29. Usage: `./install.sh` (sync), `./install.sh --dry-run` (diagnostics), `./install.sh --uninstall` (remove symlinks).

## External touchpoints (not our layers, but worth knowing)

| Touchpoint | Where it lives | Why it is not a layer |
|---|---|---|
| **MCP user-scope** | `~/.claude.json` (a separate file!) | This is not `~/.claude/settings.json`, and `.claude.json` stores additional runtime data (credentials, project history). Symlinking it is risky. If we decide to — a separate ADR. |
| **Runtime memory** | `~/.claude/projects/<id>/memory/` | Claude Code mechanics — index + topic files, accumulated during runs. Not delivered by the hub; this is runtime state. |
| **Plugins marketplace** | community/official plugins via `enabledPlugins` | We use them (e.g. `context7=true`) but do not create our own plugins — this is a different abstraction (a plugin can contain skills/agents/hooks/MCP inside it). Using existing ones — yes; creating our own — a separate task. |
| **Project-scope artifacts** | `<repo>/.claude/` and `<repo>/.mcp.json` | Per-project, not global. The hub does not touch these. |

## Brief explanation of MCP (Model Context Protocol)

MCP is an Anthropic standard that allows Claude to connect to external tools and data sources (GitHub API, databases, Gmail, Context7 docs, etc.). MCP servers are registered:
- **Project-scope:** `<repo>/.mcp.json` (for a single project).
- **User-scope:** `~/.claude.json` (for all projects).

The hub does not currently manage `~/.claude.json` (it is a separate file outside `~/.claude/`). Specific MCP servers (including Context7, which we use) are connected by the user via `claude mcp add` or configured previously. If we later want to standardize a set of user-scope MCP servers through the hub — we will formalize that in a separate ADR.

## Decision tree — which layer a new artifact belongs to + how to migrate an existing one

When a new rule, skill, check, or process appears — **walk through [decision-tree.md](decision-tree.md) first**, then place it. No ad hoc decisions.

The tree covers:
- **Placement (4 axes):** activation / context isolation / artifact kind / cross-layer triggering + bloat-prevention toolkit (`when_to_use`, `disable-model-invocation`, `context: fork`, narrow `tools:`).
- **Evolution (4 parts):** observable migration signals → migration recipes → disposition of the old artifact (delete / supersede with pointer / split) → ADR mandatory with trigger + axis-walk + disposition.

## Format of each spec

Target structure (after the rewrite iteration):

```
# <Layer name>

## Where it lives / How install works
(brief orientation)

## 1. Canonical reference (from Anthropic docs) — 60-70%
   Verbatim quotes, schema, syntax, eval semantics, sources

## 2. Hub usage & ADRs — 20-30%
   How we apply it + links to our decisions + side-by-side canonical vs hub tables where appropriate

## 3. Gray zones / open questions — remainder
   What docs do not cover, our hypotheses, known runtime quirks
```

**Naming principle:** "this works" is backed by either an authoritative source (Anthropic docs via Context7) or an empirical test (in the current session or in a recorded experiment). Without either — it is not "works", it is a "gray zone".

## When to update specs

- New empirical finding (smoke test, behavior in a real session) → add to the relevant section with a date.
- New authoritative source (new docs page, retrieved via Context7) → update sources, supersede prior hypotheses as needed.
- An ADR applied, changed, or rolled back an artifact in a layer → add a reference in the "ADRs" section of that layer.
- **Conflict between a prior entry and new empirical evidence**: supersede (as per the global engineering rule), do not append.

## Known gray zone on validators and file watcher on symlinks

- ~~Exact `install.sh` procedure~~ — closed 2026-05-29.
- Validate matrix per layer — which validator checks which layer and on which event — open future work. Includes a decision on `validate-rules.py`.
- Behavior of the `~/.claude/settings.json` symlink → external file for the file watcher — empirically works (a fresh `settings.json` is picked up through the symlink without restarting the session), but without a formal smoke-test verification.
