# Layer: Rules (`~/.claude/rules/`)

> Modular instruction files that load **on demand** when Claude reads a matching file, scoped by `paths:` glob. In the hub: `export/rules/<name>.md` → symlink `~/.claude/rules/<name>.md`. Path-scoped guidance without burdening main context in unrelated projects.

> Last updated: 2026-05-29 (layer introduced, ADR 0040).

---

## Where it lives / How install

- In the hub: `export/rules/<name>.md`.
- On the machine: `~/.claude/rules/<name>.md` (symlink via `install.sh`).
- Active across all projects (user-scope).
- File watcher picks up edits without session restart (paths-rules behaviour: edit takes effect on next Read of a matching file).

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Two activation modes

Source: `code.claude.com/docs/en/claude-directory`, `code.claude.com/docs/en/memory`.

A `.md` file in `~/.claude/rules/` can load two ways depending on frontmatter:

| Frontmatter | When it loads | Equivalent to |
|---|---|---|
| No `paths:` | At session start, every session, every project | A second CLAUDE.md (same priority) |
| With `paths:` glob list | On demand — when Claude reads a file matching any glob | A path-scoped guidance file |

The on-demand mode is the **hub primitive**. Use it to keep main context lean: a Python-specific rule loads only when Claude reads `.py` files, never burdens a TypeScript project.

### 1.2. Frontmatter syntax

```yaml
---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "src/api/**/*.{js,ts}"
---

# Rule body in plain Markdown
...
```

Supported glob patterns (per docs):

| Pattern | Matches |
|---|---|
| `**/*.ts` | All TypeScript files in any directory |
| `src/**/*` | All files under `src/` |
| `*.md` | Markdown files at project root |
| `src/components/*.tsx` | React components in that exact directory |

Brace-expansion (`"src/**/*.{ts,tsx}"`) is supported.

### 1.3. Trigger — Read tool only

From docs: «Path-scoped rules trigger when Claude reads files matching the pattern, not on every tool use.»

Read = the `Read` tool. NOT triggered by Write, Grep, Glob, or chat mention of the path. This is a deliberate narrow trigger.

### 1.4. Recursive discovery

«All `.md` files are discovered recursively, so you can organize rules into subdirectories like `frontend/` or `backend/`.»

Files outside `.md` (e.g. `.txt`, `.json`) are not picked up.

### 1.5. Symlinks

«The `.claude/rules/` directory supports symlinks, so you can maintain a shared set of rules and link them into multiple projects. Symlinks are resolved and loaded normally, and circular symlinks are detected and handled gracefully.»

This is what `install.sh` relies on for the hub.

### 1.6. Conflicts between rules and CLAUDE.md

«If two rules contradict each other, Claude may pick one arbitrarily. Review your CLAUDE.md files, nested CLAUDE.md files, and `.claude/rules/` periodically to remove outdated or conflicting instructions.»

Load order is documented («user-level rules load before project rules, giving project rules higher priority»), but it is a soft signal, not enforcement. Treat contradictions as bugs, not as trump-card behaviour.

### 1.7. Known bugs and empirical status

Historical GitHub issues against `paths:` behaviour (filed Q1 2026):

| Issue | Claim | Status in v2.1.128 (2026-05-29) |
|---|---|---|
| #21858 | `paths:` in `~/.claude/rules/` (user-level) silently ignored | **Not reproducible.** Verified main session + subagent. |
| #17204 | Documented `paths:` list-with-quotes format silently fails | **Not reproducible.** Same format works. |
| #23478 | `paths:` triggers on Read only, not on Write | **Confirmed as documented** — Read-only trigger is our use case anyway. |
| #23569 | Git worktree resolution may break `paths:` | Not retested. Assume live until verified. |

Full investigation: `docs/rules-and-imports.md`. Verification details: [ADR 0040](../decisions/0040-rules-layer.md), [memory user-level-rules-paths-activation](/Users/user/.claude/projects/-Users-user-Documents-projects-MAINFRAME/memory/user-level-rules-paths-activation.md).

---

## 2. Hub usage

### 2.1. When to use the Rules layer

**Use when:**
- Guidance is **path-scoped** (extension, directory pattern, file naming convention) and globally applicable across projects.
- Loading the guidance into every session of every project would be wasteful (skill of bias against bloat).
- The guidance is **stable enough** to live in a global file — not project-specific decisions.

Examples that fit:
- TypeScript-specific patterns auto-loaded only when Claude touches `**/*.{ts,tsx}`.
- `.env` handling advice auto-loaded on Read of `**/.env*` (parental to the dev/prod policy in [ADR 0036](../decisions/0036-env-file-readability.md)).
- SQL-migration discipline auto-loaded on Read of `**/migrations/**/*.sql`.

**Do NOT use when:**

| Wrong fit | Right layer |
|---|---|
| Always-on behavioural rule (honesty, brevity, partnership) | CLAUDE.md |
| Conditional procedure with semantic trigger (code review, severity calibration) | Skill |
| System-event reaction (block on Stop, scan after Edit) | Hook |
| Tool-call gate (deny `git push --force`) | Permissions |
| Single-project knowledge (this team's deploy steps) | Project `<repo>/.claude/rules/` (not the hub) |

**Anti-pattern: over-broad glob.** A `paths:` pattern that matches in nearly every session (e.g. `**/*`, `**/*.md`, `**/*.ts` in a TypeScript-heavy daily workflow) gives no token-economy benefit — the rule loads almost always. If a rule would load that often, it belongs in CLAUDE.md (always-on, no on-demand overhead). The Rules layer pays off when the glob is **conditionally relevant** — fires on a real subset of sessions, sleeps in the rest.

### 2.2. Hub conventions for rule files

These conventions extend the hub principles (`docs/principles.md`):

1. **Project-agnostic globs** (principle #1). Globs target file *patterns*, not project layouts. `**/*.py` is fine; `apps/myproject/src/**/*.py` is not.
2. **English body** (principle #3). Like all artifacts shipped to the agent.
3. **Concentrated body** (principle #4 — single source of truth). A rule body should be focused; long discourse belongs in CLAUDE.md or a skill, not a path-triggered rule.
4. **Always include `paths:`** for hub rules. A rule without `paths:` becomes a second CLAUDE.md (loaded everywhere, every session) — CLAUDE.md already owns that slot. If you want always-on, edit CLAUDE.md.
5. **Version-caveat for paths bugs**: rules should not rely on edge-cases known to be flaky in older versions (avoid Write-triggered expectations, avoid heavy worktree assumptions until #23569 is retested).

### 2.3. Size limits (empirical recommendation)

No Anthropic-documented limit. Practical hub target for `paths:`-rules:

- **Body ≤ ~200 lines / ~2K tokens.** Rules load every time Claude reads a matching file — the smaller, the less burden per Read.
- **Single tight topic per rule.** Split by topic into multiple rules with distinct globs; do not pack a rule with cross-domain advice.
- **No `@`-imports inside a rule** (per principle, avoid the undocumented mechanism — see `docs/rules-and-imports.md` §B.5).

If a rule outgrows these targets, see Recipe M2 in the decision-tree (split by topic) or M5 (migrate domain knowledge to a sub-agent + scoped skill).

### 2.4. Validator

No validator exists yet for `export/rules/`. When the first rule is added to the hub, evaluate whether `tools/validate-rules.py` is justified by frequency of rule edits. Until then — manual review against §2.2 + §2.3.

### 2.5. ADRs

- [ADR 0040](../decisions/0040-rules-layer.md) — introduction of the Rules layer; rejection of README-per-folder strategy.

---

## 3. Gray zones / open questions

1. **Hot-reload of rule edits in active session.** Not documented. Edit takes effect on next Read of a matching file (file watcher), but order-of-operations for rules already loaded once in the session is not specified.
2. **`@`-imports inside rule files.** Not officially documented (see `docs/rules-and-imports.md` §B.5). Not used in hub rules.
3. **`paths:` matching in git worktrees** (#23569). Not retested in v2.1.128. Hub rules should avoid layouts where worktree resolution would affect glob matching.
4. **Rule loaded once, then matching file Read again later in the same session.** Reloaded? Cached? Not documented; assume single load per session as a working model.
5. **Conflict resolution between two paths-rules whose globs overlap.** Anthropic docs say «may pick one arbitrarily» for contradictions. Hub strategy: design non-overlapping globs.

---

## Источники

**Authoritative (Anthropic Claude Code docs through Context7):**
- `code.claude.com/docs/en/memory` — rule loading, `paths:` frontmatter, conflict guidance.
- `code.claude.com/docs/en/claude-directory` — `.claude/rules/` overview, two activation modes.
- `code.claude.com/docs/en/glossary` — definition of rules.
- `code.claude.com/docs/en/agent-sdk/claude-code-features` — user vs project rule loading.

**Empirical (2026-05-29, Claude Code v2.1.128):**
- V2 subagent test — pre/post Read differential. PRE=NONE, POST=magic. Confirmed on-demand in subagent.
- Headless `claude -p` main-session test — same differential, same result. Confirmed on-demand in main session.

**Internal:**
- [docs/rules-and-imports.md](../rules-and-imports.md) — fuller `.claude/rules/` + `@import` analysis with bug-tracker references.
- [docs/decisions/0040-rules-layer.md](../decisions/0040-rules-layer.md) — ADR introducing the layer.
- [docs/principles.md](../principles.md) — hub principles, §1 (agnosticism), §3 (English), §4 (single source of truth).
