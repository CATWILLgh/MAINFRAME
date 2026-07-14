# Layer: Output styles

> **Staleness note (ADR 0085, 2026-07-08):** this spec describes the pre-neutral-core architecture, where files under `dist/claude-code/plugin/` / `dist/` are the source of truth. Sources are migrating to `core/` + `adapters/<tool>/`; `dist/claude-code/plugin/` and `dist/` remain the delivered, committed render targets. The spec is updated wave by wave as its layer lands on the core.


> Custom output styles for Claude (e.g. "diagram-first", "code-reviewer", "brevity"). In the hub: `dist/claude-code/output-styles/<name>.md`.

> Last updated: 2026-06-11. First artifact shipped: `explanatory-concise` (verified against CLI bundle 2.1.165).

---

## Where it lives / How to install

- In the hub: `dist/claude-code/output-styles/<name>.md` — one file per style.
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
- `keep-coding-instructions` — `true` keeps the standard coding instructions and adds the style on top; `false` drops them, leaving only the style body. **Default is `false`** (verified in CLI bundle 2.1.165, schema `RU5`; the built-ins set it `true` explicitly). A coding-capable custom style MUST set `keep-coding-instructions: true` — omitting it silently drops the engineering discipline.

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

**Shipped:**
- `explanatory-concise` — forks the built-in `Explanatory` style: keeps the `## Insights` block verbatim (the `★ Insight` teaching the user values) and `keep-coding-instructions: true`, but drops the built-in's "you may exceed typical length constraints" license and adds a short-and-plain-language directive. Solves the recurring "reply got long and dense mid-session" friction structurally: the body lives in the system prompt every turn and survives compaction, so it does not decay like a start-of-session reminder. Activated by the user via `/config` (not forced). Provenance: built-in `Explanatory` body extracted from CLI bundle 2.1.165.

Possible future candidates: `code-review` (structured audit output), `diagram-first` (ASCII schematics primary).

Hub principles:
- **One style = one explicit goal** (not "all-purpose").
- **`description` kept short** — displayed in the `/config` menu.
- **Do not duplicate CLAUDE.md behavior** — general rules belong there; a style covers tone / format / length posture.

ADRs: none yet (the first style was a direct user request; record an ADR if a second arrives or the rationale grows).

---

## 3. Resolved (verified against CLI bundle 2.1.165, 2026-06-11)

1. **`keep-coding-instructions: false`** drops the standard engineering-instructions block entirely; only the style body (plus fixed system sections like tool guidance) remains. Default when omitted is `false`.
2. **Composition** — only one style is active at a time (`outputStyle` is a single value). The active style's body is injected into the system prompt as `# Output Style: {name}` (function `TQ3`), plus a per-turn meta reminder (`L83`; custom styles get the generic "Remember to follow the specific guidelines for this style").
3. **Persistence** — the system prompt is rebuilt from live settings every request, so the style **survives context compaction** and does not decay like a start-of-session message. Changes to the file or `outputStyle` take effect only after `/clear` or a new session. `/output-style` was removed in v2.1.91 — use `/config`. `outputStylesPath` (settings) overrides the auto-scan of the `output-styles/` dirs.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/output-styles` — format, frontmatter, `keep-coding-instructions`.
- `code.claude.com/docs/en/agent-sdk/modifying-system-prompts` — how styles fit into the system prompt.

**Internal:**
- [decision-tree.md](decision-tree.md) — Q3 (artifact type: vibe/format → Output style).
