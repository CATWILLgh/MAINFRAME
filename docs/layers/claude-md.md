# Layer: CLAUDE.md (Operating instructions)

> Global Claude instruction delivered to every session across all projects. In the hub: `export/CLAUDE.md` → symlink `~/.claude/CLAUDE.md`.

> Last updated: 2026-05-28 (3-section rewrite).

---

## Where it lives / How to install

- In the hub: `export/CLAUDE.md` (132 lines as of 2026-05-28).
- On the machine: `~/.claude/CLAUDE.md` (symlink via `install.sh`).
- Active in all projects via user-scope.
- Claude Code's file watcher picks up edits without restarting the session.

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

### 2.1. Current `export/CLAUDE.md`

Structure (as of 2026-05-28, 132 lines):

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
| Advisor | Before substantive work / before declaring done |
| Git and commits | No Claude attribution |
| Destructive actions | Name explicitly, wait for ack |

### 2.2. Validator

[`tools/validate-claude-md.py`](../../tools/validate-claude-md.py) — checks the Anthropic spec (R1-R5) + the project agnosticism principle (R6). Triggered on `SessionStart` (summary) + `PostToolUse` (Edit/Write/MultiEdit; exits instantly otherwise). Uses system `python3`, no dependencies.

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
