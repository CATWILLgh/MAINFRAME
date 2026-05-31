# Layer: Settings (прочие поля)

> Конфигурация Claude Code за пределами `permissions` и `hooks` (которые имеют отдельные спеки). В хабе: `export/settings.json` остальные поля.

> Последнее обновление: 2026-05-28 (3-секционный rewrite).

---

## Где живёт / Как install

- В хабе: `export/settings.json` — единый файл, в котором сосуществуют `permissions`, `hooks` и прочие поля.
- На машине: `~/.claude/settings.json` (симлинк целого файла).
- Активация: одним симлинком; правки в `export/settings.json` подхватываются file watcher'ом без рестарта.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Scopes (4 уровня)

Источник: `code.claude.com/docs/en/settings`.

| Scope | Локация | Влияние | Shared? |
|---|---|---|---|
| **Managed** | macOS: `/Library/Application Support/ClaudeCode/managed-settings.json` или MDM | Все пользователи машины | Yes (IT-deploy) |
| **User** | `~/.claude/settings.json` | Один пользователь, во всех проектах | No |
| **Project** | `<repo>/.claude/settings.json` | Все, кто работает в репо | Yes (git) |
| **Local** | `<repo>/.claude/settings.local.json` | Только этот пользователь в этом репо | No (gitignored) |

### 1.2. Priority order

От высшего к низшему:
1. **Managed** — нельзя переопределить ничем.
2. **Command-line arguments** (`--allowedTools`, `--permission-mode`, ...) — сессионные.
3. **Local** — переопределяет project и user.
4. **Project** — переопределяет user.
5. **User** — действует, когда нигде больше не задано.

### 1.3. Merge vs override

**Стандартные настройки (не permissions): override (closer scope wins).**

> «If your user settings set `spinnerTipsEnabled` to `true` and project settings set it to `false`, the project value applies.»

**Permissions rules: merge across scopes** (см. отдельную спеку [permissions.md](permissions.md)).

### 1.4. Hot-reload через file watcher

> «Claude Code monitors your settings files and reloads them upon changes, allowing edits to most keys to apply to the running session without a restart. This includes `permissions`, `hooks`, and credential helpers like `apiKeyHelper`.»

Точный размер «brief delay» не документирован.

### 1.5. Известные канонические поля

Из docs (`code.claude.com/docs/en/settings`):
- `$schema` — JSON Schema URL для IDE-валидации.
- `env` — env vars для bash-инструмента и hook'ов.
- `permissions.{allow,deny,ask,defaultMode}` — см. [permissions.md](permissions.md).
- `hooks` — см. [hooks.md](hooks.md).
- `enabledPlugins` — toggles для plugins marketplace.
- `outputStyle` — выбор активного output style (см. [output-styles.md](output-styles.md)).
- `autoMemoryEnabled` — runtime memory toggle.
- `companyAnnouncements` — массив строк, показываются при старте.
- `apiKeyHelper` — credential helper command.
- `statusLine.command` — кастомный статус-скрипт.
- `allowManagedPermissionRulesOnly` — only managed permissions apply (corp lockdown).

---

## 2. Hub usage & ADRs

### 2.1. Текущие поля в `export/settings.json` (помимо permissions/hooks)

| Поле | Значение | Назначение |
|---|---|---|
| `$schema` | `https://json.schemastore.org/claude-code-settings.json` | IDE-валидация |
| `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `"1"` | Эксп. флаг agent teams |
| `permissions.defaultMode` | `"acceptEdits"` | Default mode сессии |
| `enabledPlugins.superpowers@claude-plugins-official` | `false` | Disabled |
| `enabledPlugins.context7@claude-plugins-official` | `true` | Enabled (Context7 plugin) |
| `language` | `"Russian"` | Язык интерфейса/ответов |
| `advisorModel` | `"opus"` | Модель для `advisor()` |
| `preferredNotifChannel` | `"kitty"` | Канал нотификаций |
| `teammateMode` | `"in-process"` | Mode для teammates |
| `remoteControlAtStartup` | `false` | Remote control |
| `effortLevel` | `"max"` | Effort level Claude'а |

### 2.2. Backups в репо

При каждой нетривиальной правке `export/settings.json` создаётся `export/settings.json.backup-<timestamp>` (см. два существующих backup'а от 2026-05-27 и 2026-05-28).

### 2.3. ADR'ы, влияющие на слой

Косвенно (через permissions/hooks/output-styles, которые живут в settings.json):
- [0012](../decisions/0012-permissions-ask-no-verify.md) — permissions блок (см. [permissions.md](permissions.md)).
- [0014](../decisions/0014-stop-gate-suppression-markers.md) — hooks блок (см. [hooks.md](hooks.md)).

Прямо для прочих полей — пока нет ADR'ов; правки делались инкрементально.

---

## 3. Gray zones / open questions

1. **Полный реестр всех допустимых ключей** — есть `$schema`, но не вся спека человекочитаемо одним списком. Часть полей (`teammateMode`, `effortLevel`, `preferredNotifChannel`, `remoteControlAtStartup`) не описана в основных docs страницах — приходится reverse-engineering из IDE-подсказок.
2. **Поведение симлинков** `~/.claude/settings.json` → external file — не упомянуто в docs. Empirically: работает, file watcher подхватывает.
3. **Несколько JSON-файлов на одном scope** (например, `~/.claude/settings.json` + `~/.claude/settings.deny.json`) — не задокументировано, не работает (только один файл на scope).
4. **`extends:` / `include:` для импорта другого settings** — не существует.
5. **Partial overlay (.d/-папка)** — нет.
6. **Точный размер «brief delay»** file watcher'а — не задокументирован.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/settings` — scopes, priority order, hot-reload, основные ключи.
- `code.claude.com/docs/en/env-vars` — env vars vs settings env block.

**Internal:**
- Эмпирика хаба 2026-05-26 (порядок precedence, merge для permissions vs override для прочего).
- ADR'ы 0012, 0014.
