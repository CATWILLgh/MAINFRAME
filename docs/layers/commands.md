# Layer: Commands

> Legacy custom command files. The hub currently uses user-invocable skills for manual workflows; `/mainframe:init` lives at `adapters/claude-code/plugin/skills/init/SKILL.md`.

> Last updated: 2026-08-09. The layer is reserved; no command files exist.

---

## Where it lives / How to install

- In the hub: `adapters/claude-code/plugin/commands/<name>.md` — one file per command.
- On the machine: delivered via the `mainframe` plugin (`adapters/claude-code/plugin/` symlinked as one plugin).
- Activation: once the plugin is loaded, the command is available in chat — as a plugin command it carries the plugin prefix `/mainframe:<name>` (see §1.4).

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

**No command-file artifacts.** Manual, user-only context loading is implemented as the `init` skill because skills are the current Claude Code mechanism and support `disable-model-invocation: true`.

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
