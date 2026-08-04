# Layer: Settings (other fields)

> **Architecture note (five-tool hub, 2026-08-05):** MAINFRAME targets Claude Code, OpenCode, Codex, ZCode Desktop, and the standalone Antigravity 2.x desktop application. Shared sources live in `core/`, tool-specific sources in `adapters/<tool>/`, and native builders populate `dist/<tool>/`. Do not hand-edit generated outputs.


> User-owned Claude Code configuration outside the rendered permission lists. Hook registration has moved to the `mainframe` plugin and is not stored in this file.

> Last updated: 2026-07-14 (hybrid ownership and current fields).

---

## Where it lives / How to install

- In the hub: `dist/claude-code/settings.json` — a hybrid file containing rendered permission lists and directly maintained user settings.
- On the machine: `~/.claude/settings.json` (symlink of the whole file).
- Ownership: `core/permissions/rules.json` owns only `permissions.allow`, `permissions.deny`, and `permissions.ask`. Edit every other field directly in `dist/claude-code/settings.json`; `render_core.py` preserves it.
- Scope: this general-settings layer is Claude Code only. OpenCode and Codex receive separate permission projections, not copies of these user settings; ZCode and Antigravity settings remain user-owned except for narrowly claimed adapter entries.
- Activation: a single symlink; Claude Code picks up most edits through its file watcher without a restart.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Scopes (4 levels)

Source: `code.claude.com/docs/en/settings`.

| Scope | Location | Impact | Shared? |
|---|---|---|---|
| **Managed** | macOS: `/Library/Application Support/ClaudeCode/managed-settings.json` or MDM | All users on the machine | Yes (IT-deploy) |
| **User** | `~/.claude/settings.json` | One user, across all projects | No |
| **Project** | `<repo>/.claude/settings.json` | Everyone working in the repo | Yes (git) |
| **Local** | `<repo>/.claude/settings.local.json` | Only this user in this repo | No (gitignored) |

### 1.2. Priority order

From highest to lowest:
1. **Managed** — cannot be overridden by anything.
2. **Command-line arguments** (`--allowedTools`, `--permission-mode`, ...) — session-scoped.
3. **Local** — overrides project and user.
4. **Project** — overrides user.
5. **User** — applies when nothing else is set.

### 1.3. Merge vs override

**Standard settings (not permissions): override (closer scope wins).**

> "If your user settings set `spinnerTipsEnabled` to `true` and project settings set it to `false`, the project value applies."

**Permissions rules: merge across scopes** (see the separate spec [permissions.md](permissions.md)).

### 1.4. Hot-reload via file watcher

> "Claude Code monitors your settings files and reloads them upon changes, allowing edits to most keys to apply to the running session without a restart. This includes `permissions`, `hooks`, and credential helpers like `apiKeyHelper`."

The exact size of the "brief delay" is not documented.

### 1.5. Known canonical fields

From docs (`code.claude.com/docs/en/settings`):
- `$schema` — JSON Schema URL for IDE validation.
- `env` — env vars for the bash tool and hooks.
- `permissions.{allow,deny,ask,defaultMode}` — see [permissions.md](permissions.md).
- `hooks` — see [hooks.md](hooks.md).
- `enabledPlugins` — toggles for plugins marketplace.
- `outputStyle` — selects the active output style (see [output-styles.md](output-styles.md)).
- `autoMemoryEnabled` — runtime memory toggle.
- `companyAnnouncements` — array of strings, displayed at startup.
- `apiKeyHelper` — credential helper command.
- `statusLine.command` — custom status script.
- `allowManagedPermissionRulesOnly` — only managed permissions apply (corp lockdown).

---

## 2. Hub usage & ADRs

### 2.1. Current user-owned fields in `dist/claude-code/settings.json`

| Field | Value | Purpose |
|---|---|---|
| `$schema` | `https://json.schemastore.org/claude-code-settings.json` | IDE validation |
| `cleanupPeriodDays` | `3650` | Retention period |
| `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `"1"` | Experimental agent teams flag |
| `model` | `"opus[1m]"` | Default model selection |
| `permissions.defaultMode` | `"auto"` | Default session mode; not part of the rendered rule lists |
| `enabledPlugins.context7@claude-plugins-official` | `true` | Enabled (Context7 plugin) |
| `enabledPlugins.frontend-design@claude-plugins-official` | `false` | Disabled |
| `outputStyle` | `"Explanatory Concise"` | Active output style |
| `language` | `"Russian"` | Interface/response language |
| `advisorModel` | `"opus"` | Model used for `advisor()` |
| `autoMemoryEnabled` | `true` | Native auto-memory toggle |
| `skipWorkflowUsageWarning` | `true` | Workflow warning toggle |
| `editorMode` | `"normal"` | Editor interaction mode |
| `verbose` | `false` | Verbose output toggle |
| `preferredNotifChannel` | `"kitty"` | Notification channel |
| `autoCompactEnabled` | `true` | Automatic context compaction |
| `teammateMode` | `"in-process"` | Mode for teammates |
| `remoteControlAtStartup` | `false` | Remote control |
| `effortLevel` | `"high"` | Claude's effort level |

### 2.2. Rendering and permissions

`render_core.py` does not create timestamped backups in the repository. It key-merges `allow`, `deny`, and `ask` from `core/permissions/rules.json` into `dist/claude-code/settings.json`; `permissions.defaultMode` and every non-permission setting remain untouched. This mixed ownership is intentional, so the usual “do not edit generated `dist/` files” rule applies only to the three rendered lists inside this file.

---

## 3. Gray zones / open questions

1. **Full registry of all allowed keys** — `$schema` exists, but the full spec is not available as a single human-readable list. Some fields (`teammateMode`, `effortLevel`, `preferredNotifChannel`, `remoteControlAtStartup`) are not described on the main docs pages — they require reverse-engineering from IDE hints.
2. **Symlink behavior** `~/.claude/settings.json` → external file — not mentioned in docs. Empirically: works, the file watcher picks it up.
3. **Multiple JSON files at the same scope** (e.g. `~/.claude/settings.json` + `~/.claude/settings.deny.json`) — not documented, does not work (only one file per scope).
4. **`extends:` / `include:` for importing another settings file** — does not exist.
5. **Partial overlay (.d/ directory)** — does not exist.
6. **Exact size of the "brief delay"** of the file watcher — not documented.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/settings` — scopes, priority order, hot-reload, main keys.
- `code.claude.com/docs/en/env-vars` — env vars vs settings env block.

**Internal:**
- Hub empirics 2026-05-26 (precedence order, merge for permissions vs override for other fields).
- ADRs 0012, 0014.
