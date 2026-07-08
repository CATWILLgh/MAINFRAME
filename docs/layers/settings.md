# Layer: Settings (other fields)

> **Staleness note (ADR 0085, 2026-07-08):** this spec describes the pre-neutral-core architecture, where files under `plugin-dist/` / `export/` are the source of truth. Sources are migrating to `core/` + `adapters/<tool>/`; `plugin-dist/` and `export/` remain the delivered, committed render targets. The spec is updated wave by wave as its layer lands on the core.


> Configuration of Claude Code outside `permissions` and `hooks` (which have their own separate specs). In the hub: `export/settings.json` — the remaining fields.

> Last updated: 2026-05-28 (3-section rewrite).

---

## Where it lives / How to install

- In the hub: `export/settings.json` — a single file where `permissions`, `hooks`, and other fields coexist.
- On the machine: `~/.claude/settings.json` (symlink of the whole file).
- Activation: a single symlink; edits to `export/settings.json` are picked up by the file watcher without a restart.

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

### 2.1. Current fields in `export/settings.json` (besides permissions/hooks)

| Field | Value | Purpose |
|---|---|---|
| `$schema` | `https://json.schemastore.org/claude-code-settings.json` | IDE validation |
| `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `"1"` | Experimental agent teams flag |
| `permissions.defaultMode` | `"acceptEdits"` | Default session mode |
| `enabledPlugins.superpowers@claude-plugins-official` | `false` | Disabled |
| `enabledPlugins.context7@claude-plugins-official` | `true` | Enabled (Context7 plugin) |
| `language` | `"Russian"` | Interface/response language |
| `advisorModel` | `"opus"` | Model used for `advisor()` |
| `preferredNotifChannel` | `"kitty"` | Notification channel |
| `teammateMode` | `"in-process"` | Mode for teammates |
| `remoteControlAtStartup` | `false` | Remote control |
| `effortLevel` | `"max"` | Claude's effort level |

### 2.2. Backups in the repo

On every non-trivial edit to `export/settings.json`, a `export/settings.json.backup-<timestamp>` is created (see the two existing backups from 2026-05-27 and 2026-05-28).

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
