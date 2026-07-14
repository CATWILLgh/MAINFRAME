# Layer: Commands

> **Architecture note (three-tool hub, 2026-07-14):** MAINFRAME targets Claude Code, OpenCode, and Codex. Shared sources live in `core/`, tool-specific sources in `adapters/<tool>/`, and `render_core.py` plus the OpenCode/Codex builders populate `dist/<tool>/`. Do not hand-edit generated outputs. The path-scoped Rules layer is authored directly in `dist/claude-code/rules/`; non-permission fields in `dist/claude-code/settings.json` are also user-owned there.


> Custom slash commands (`/<name>`), explicitly invoked by the user. This is a reserved Claude Code layer: no command artifact, source directory, renderer mapping, or runtime output exists yet.

> Last updated: 2026-07-14 (reserved-layer ownership clarified). Layer is reserved; no artifacts yet.

---

## Where it lives / How to install

- No `core/commands/`, adapter command directory, `dist/claude-code/plugin/commands/`, or OpenCode/Codex projection exists.
- Before the first command is added, define an authored source and renderer mapping. Do not create a command directly under generated `dist/` output.
- The expected Claude Code runtime destination would be the `mainframe` plugin, where plugin commands carry the `/mainframe:<name>` prefix (see §1.4); this is a future contract, not current delivery.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Frontmatter

Source: `code.claude.com/docs/en/slash-commands`.

```yaml
---
name: <kebab-case>                # display name; defaults to filename
description: <one line>           # shown in the /-command menu
allowed-tools: <subset>           # tools without a permission ask
argument-hint: <[arg1] [arg2]>    # autocomplete hint
arguments: <space-separated or yaml-list>  # named positionals for $name substitution
model: <opus|sonnet|haiku|inherit>          # model override for the command turn
---

Body — markdown instruction. `$ARGUMENTS` = everything after `/<name>`. Named args via `arguments:` mapping.
```

### 1.2. Difference from a Skill

| | Command | Skill |
|---|---|---|
| Activation | **explicit only** — `/<name>` by the user | auto-trigger based on `description + when_to_use` |
| Visible in `/` menu | yes (always) | only if `user-invocable: true` |
| Frontmatter | `description`, `allowed-tools`, `arguments`, `argument-hint`, `model` | same + `when_to_use`, `disable-model-invocation`, `context`, `effort` |
| Purpose | side-effect actions (commit, deploy, scaffold, release) | conditional knowledge / workflow |

A command is for operations with **a visible external effect** that the user must explicitly request. A skill is for contextually loaded knowledge or procedures.

### 1.3. Activation

1. The user types `/<name> <args>` in chat.
2. Claude sees the frontmatter (`description`, `argument-hint`).
3. On invocation, the body is loaded with arguments substituted in.
4. Commands are not auto-invoked by the model (this is exactly what distinguishes them from skills).

### 1.4. Plugin namespacing

Commands inside plugins carry the plugin prefix (e.g. `/plugin:context7:query`). The hub ships as the `mainframe` plugin, so a hub command would be invoked as `/mainframe:<name>`.

---

## 2. Hub usage & ADRs

**No artifacts.** The layer is reserved. Its first use requires an explicit source/render decision before an artifact is created.

Hub principles (when the first command is added):
- **Command = side-effect action** — if not, it belongs in a skill.
- **Narrow `allowed-tools` allowlist** — the command does only what it was created to do.
- **Short `description`** — it appears in the `/` menu, not the place for a tutorial.

ADRs: none.

---

## 3. Gray zones / open questions

1. **`arguments:` mapping behavior with YAML list vs space-separated string** — not empirically tested.
2. **Name collision** — `/build` in the hub vs `/build` in a plugin — which one wins? Not explicitly documented.
3. **`model:` override scope** — does it apply only to the command turn or longer? Clarify on first use.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/slash-commands` — format, frontmatter, `$ARGUMENTS`.
- `code.claude.com/docs/en/features-overview` — Command vs Skill comparison.

**Internal:**
- [decision-tree.md Recipe F](decision-tree.md) — when to choose command vs skill with `user-invocable: true`.
