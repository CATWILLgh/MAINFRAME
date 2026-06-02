# Layer: Output styles

> Custom output styles for Claude (e.g. "diagram-first", "code-reviewer", "brevity"). In the hub: `export/output-styles/<name>.md` (currently **empty**).

> Last updated: 2026-05-28 (3-section rewrite). Layer is reserved; no artifacts yet.

---

## Where it lives / How to install

- In the hub: `export/output-styles/<name>.md` — one file per style.
- On the machine: `~/.claude/output-styles/<name>.md` (symlinked via `install.sh`).
- Activation: via `/config` (selecting the active style) or `outputStyle: "<name>"` in `settings.json`.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Frontmatter

Source: `code.claude.com/docs/en/output-styles`.

```yaml
---
name: <kebab-case>                       # display name
description: <one line>                  # shown in /config menu
keep-coding-instructions: <true|false>   # whether to preserve standard coding instructions when the style is active
---

Body — a markdown instruction, appended to the system prompt when the style is activated.
```

### 1.2. Activation and scope

- The active style is selected via `/config` (runtime) or fixed globally via `outputStyle: "<name>"` in `settings.json`.
- A style applies **for the entire session** until changed.
- When activated, the file body **is appended to the system prompt** — the model sees the instructions as part of its baseline rules.
- `keep-coding-instructions: false` — replaces the standard coding instructions with the style's own; `true` (default) — adds on top of them.

### 1.3. Skills vs Output styles

| | Output style | Skill |
|---|---|---|
| Purpose | output format / tone / structure (how to respond) | conditional knowledge / workflow (what to do) |
| Activation | sticky via `/config` or settings (whole session) | per-trigger via `description + when_to_use` |
| In system prompt | yes, when activated | no; body is loaded on trigger |
| Frontmatter | `name`, `description`, `keep-coding-instructions` | broad (see [skills.md](skills.md)) |

Output style — for the **global session vibe**. Skill — for **targeted knowledge / procedure**.

---

## 2. Hub usage & ADRs

**No artifacts.** Layer is reserved. Possible future candidates:
- `code-review` — structured output for audits.
- `brevity` — maximally concise responses.
- `diagram-first` — diagrams / ASCII schematics as the primary output format.

Hub principles (when the first style is added):
- **One style = one explicit goal** (not "all-purpose").
- **`description` kept short** — displayed in the `/config` menu.
- **Do not duplicate CLAUDE.md behavior** — general rules belong there; a style covers format only.

ADRs: none.

---

## 3. Gray zones / open questions

1. **`keep-coding-instructions: false`** — what exactly is removed? The precise scope (only technical behavior, or all discipline) is not described explicitly.
2. **Composition** — can two styles be active at the same time? Not documented; presumably no.
3. **Persistence across sessions** — `outputStyle:` in settings is sticky; via `/config` — only for the current session? To be confirmed.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/output-styles` — format, frontmatter, `keep-coding-instructions`.
- `code.claude.com/docs/en/agent-sdk/modifying-system-prompts` — how styles fit into the system prompt.

**Internal:**
- [decision-tree.md](decision-tree.md) — Q3 (artifact type: vibe/format → Output style).
