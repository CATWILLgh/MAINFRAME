# Layer: Umbrella operating instructions (`CLAUDE.md` / `AGENTS.md`)

> **Architecture note (four-tool hub, 2026-07-15):** MAINFRAME targets Claude Code, OpenCode, Codex, and the standalone Antigravity 2.x desktop application. Shared sources live in `core/`, tool-specific sources in `adapters/<tool>/`, and `render_core.py` plus the OpenCode/Codex/Antigravity builders populate `dist/<tool>/`. Do not hand-edit generated outputs. The path-scoped Rules layer is authored directly in `dist/claude-code/rules/`; non-permission fields in `dist/claude-code/settings.json` are also user-owned there.


> Shared global instructions delivered to every session across all projects, with thin runtime-specific wrappers for Claude Code, OpenCode, Codex, and Antigravity 2.x.

> Last updated: 2026-07-15 (Antigravity plugin-rule projection).

---

## Where it lives / How to install

- Shared source: ordered fragments in `core/instructions/`.
- Tool-specific source: instruction fragments under each `adapters/<tool>/instructions/` directory.
- Rendered targets: `dist/claude-code/CLAUDE.md` (159 lines), `dist/opencode/AGENTS.md` (149 lines), and `dist/codex/AGENTS.md` (149 lines), verified 2026-07-14 with `wc -l`.
- Runtime delivery: `~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `${CODEX_HOME:-~/.codex}/AGENTS.md`, and separate always-on rule files inside the Antigravity global plugin.
- `python3 tools/render_core.py --write` composes the three umbrella files. The Antigravity builder projects each shared fragment as an individual rule so one oversized file cannot exceed that runtime's rule budget.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Loading and scopes

Source: `code.claude.com/docs/en/memory`.

Claude Code loads CLAUDE.md from three levels:
- **User-scope:** `~/.claude/CLAUDE.md` — active across all projects for a given user.
- **Project-scope:** `<repo>/CLAUDE.md` — active only within that repo.
- **Local-scope (optional):** `<repo>/.claude/CLAUDE.md` — gitignored, local overrides.

**Behavior when multiple are present:** project + local **supplement** user-scope (accumulation), they do not override it. User-scope is the shared base layer.

### 1.2. Syntax

- Markdown with no required frontmatter.
- Structure is freeform; recommended sections are `# Operating instructions` followed by topic-specific `## ...`.
- Short, explicit rules (bullets) are preferable to long prose blocks.

### 1.3. `@import` — importing another file

> The `@path/to/file.md` syntax imports the contents of another markdown file into the same context.

Supported:
- Relative paths (`@docs/notes.md`, `@CHANGELOG.md`, etc.).
- Import depth is bounded (no cycles).

### 1.4. Length and adherence

> "Longer files reduce adherence" — official Anthropic recommendation.

There is no hard limit; the practical target is to keep total volume (user + project) under a few hundred lines so that critical rules do not get buried.

### 1.5. What is NOT a CLAUDE.md

- `~/.claude/projects/<id>/CLAUDE.md` or similar (if it appears in the future) — this is **Claude Code runtime state** accumulated during operation, not part of the hub.

---

## 2. Hub usage

### 2.1. Current rendered instructions

The shared core supplies the common sections below. Claude Code inserts its orchestration, memory, and advisor sections before the common Git/destructive-action tail; OpenCode and Codex append runtime notes; Antigravity packages the same sections as ordered plugin rules plus desktop-specific memory and orchestration rules.

| Section | Contents |
|---|---|
| Partnership | Engineering partner, push back, surface tradeoffs |
| Communication | Plain language, brief, no fluff |
| Honesty | No fabrication, severity calibration |
| No flattery | No evaluative openers |
| Thinking and decision making | Anti-rationalization, step-by-step, lowest-risk |
| Evidence and sources | Context7 primary, authoritative web fallback |
| Verification | Empty-result re-query without filter |
| Output format | Concrete actionable, what/why/verify |
| Engineering practices | DRY/SOLID/KISS, no suppression markers, supersede-not-append, 400/60 file/fn limits |
| Problem-solving | Read 3-5 files; error-handling 5-step; do-not list (stop conditions, pre-flight) |
| Orchestration | Subagents for broad work |
| Git and commits | No Claude attribution |
| Destructive actions | Name explicitly, wait for ack |

Claude Code additionally renders `Orchestration — Claude Code`, `Memory`, and `Advisor`. Each alternate adapter adds only its runtime mechanics.

### 2.2. Validator

[`tools/validate-claude-md.py`](../../tools/validate-claude-md.py) checks the Anthropic format and project-agnosticism rules for the Claude Code umbrella and its source fragments. `python3 tools/render_core.py --check` guards the umbrella renders; the Antigravity builder tests guard its per-rule projection.

---

## 3. Gray zones / open questions

1. **Exact mechanism of rate-limiting / selective section loading** for a long CLAUDE.md — not documented by Anthropic. Empirically: short bullets adhere better than long prose blocks.
2. **Behavior of `@import` when the target file is missing** — not documented. Not tested empirically.
3. **Project-scope CLAUDE.md at `<repo>/.claude/CLAUDE.md`** (if that location exists in addition to `<repo>/CLAUDE.md`) — no mentions found in the docs.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/memory` — Claude Code memory mechanics, CLAUDE.md loading, `@import`.

**Internal:**
- `tools/validate-claude-md.py` — runtime validator.
