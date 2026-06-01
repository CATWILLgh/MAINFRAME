# Layer: Hooks

> Скрипты, выполняемые Claude Code при определённых событиях (tool-use, stop, session-start, file-change и т.п.). В хабе: `export/hooks/*.py` + регистрация в `export/settings.json` `hooks.*`.

> Последнее обновление: 2026-05-28 (3-секционный rewrite после subagent deep-dive: 16 event types).

---

## Где живёт / Как install

- В хабе: `export/hooks/*.py` (скрипты) + `export/settings.json` блок `hooks.{EventName}` (регистрация).
- На машине: `~/.claude/hooks/*.py` (симлинки) + `~/.claude/settings.json` (часть симлинка целиком).
- Активация:
  1. Симлинк папки `export/hooks/` → `~/.claude/hooks/` (через `install.sh`).
  2. Запись в `hooks.<EventName>` внутри `export/settings.json`.
  3. File watcher Claude Code подхватывает изменения «with brief delay» без рестарта.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Полный список событий (Python SDK)

Источник: `code.claude.com/docs/en/agent-sdk/python` + `code.claude.com/docs/en/hooks`.

| Event | Trigger | Matcher | Decision control | Notes |
|---|---|---|---|---|
| `PreToolUse` | До tool execution | да (tool name) | allow / deny / ask / defer | Можно modify `updatedInput` |
| `PostToolUse` | После успешного tool | да (tool name) | block | Можно modify `updatedToolOutput` |
| `PostToolUseFailure` | После failed tool | да (tool name) | context-only | `additionalContext` |
| `UserPromptSubmit` | Submit prompt | — | block | Получает `prompt` |
| `Stop` | Claude заканчивает ход | **нет matcher** | `{"decision":"block","reason":...}` | `stop_hook_active` guard |
| `SubagentStop` | Сабагент заканчивает | да (`agent_type`) | block / continue:false | |
| `SubagentStart` | Сабагент стартует | да (`agent_type`) | context-only | Инъекция глобального контекста |
| `SessionStart` | Session начинается | да (`source`: startup/resume/clear/compact) | context-only | |
| `SessionEnd` | Session заканчивается | да (`reason`) | **не может блокировать** | Cleanup only |
| `Notification` | Notification triggered | да (type) | context-only | |
| `PreCompact` | Перед компакцией | — | — | Payload schema не приведена детально |
| `PostCompact` | После компакции | — | — | То же |
| `Setup` | Session setup | — | — | Payload не детализирован |
| `FileChanged` | Файл изменён | да (pattern) | — | Live file watching |
| `ConfigChange` | `settings.json` изменился | да (empty = all) | — | Fires на hot-reload |
| `PermissionRequest` | Permission prompt triggered | да (tool name) | allow/deny + `updatedPermissions` | Можно менять mode |

TypeScript SDK поддерживает additional events; полный список не выложен в найденных docs.

### 1.2. Синтаксис регистрации

`PostToolUse` (с matcher):
```json
"hooks": {
  "PostToolUse": [{
    "matcher": "Edit|Write|MultiEdit",
    "hooks": [{
      "type": "command",
      "command": "[ -f $HOME/.claude/hooks/scan.py ] && python3 $HOME/.claude/hooks/scan.py || true"
    }]
  }]
}
```

`Stop` (без matcher):
```json
"hooks": {
  "Stop": [{
    "hooks": [{
      "type": "command",
      "command": "[ -f $HOME/.claude/hooks/gate.py ] && python3 $HOME/.claude/hooks/gate.py || true"
    }]
  }]
}
```

Другие типы hook-entry:
- `prompt`: `{ "type": "prompt", "prompt": "Evaluate: $ARGUMENTS" }` — LLM-based decision.
- `agent`: `{ "type": "agent", "prompt": "...", "timeout": 120 }` — subagent-based.

### 1.3. Stop hook — критические детали

> Decision control: вернуть `{"decision":"block","reason":...}` на stdout + exit 0.

> `stop_hook_active` semantics: payload содержит `stop_hook_active: true`, если hook **уже блокировал** этот же turn. Hook **обязан** проверить и exit 0, иначе loop. После **8 consecutive blocks** Claude Code override-ит и завершает turn всё равно.

### 1.4. Path resolution и cwd

- **`cwd` hook'а** = текущий каталог сессии (может меняться через `cd`). **Не использовать относительные пути.**
- **`${CLAUDE_PROJECT_DIR}`** — каталог запуска Claude (стабильный). Источник: `code.claude.com/docs/en/hooks` + хабовая эмпирика.

### 1.5. File watcher / hot-reload

> «Direct edits to hooks in settings files are normally picked up automatically by the file watcher.»

Точный размер «brief delay» не задокументирован; эмпирически — мс-секунды.

### 1.6. Hooks и субагенты (находка 2026-06-01)

Раньше неявно предполагалось, что хуки — про главную сессию. Уточнено по источнику:

- **`PreToolUse` / `PostToolUse` / `Stop` срабатывают и на tool-вызовы сабагента**, не только главного агента. `PreToolUseHookInput` несёт поля `agent_id` и `agent_type` — *«present when the hook fires inside a subagent»* (`code.claude.com/docs/en/agent-sdk/python`). То есть глобальный хук может различать контекст: пустой `agent_id` → главный агент, заполненный → сабагент (`agent_type` = `name` агента).
- **Два канала навесить хук на сабагента:**
  1. **Глобальный** — `plugin-dist/hooks/hooks.json` (или `export/settings.json`). Стреляет у всех: главный агент + каждый сабагент.
  2. **Per-agent** — поле `hooks:` во frontmatter сабагента: scoped к этому агенту, все события, очищается по завершении; `Stop` во frontmatter рантайм-конвертится в `SubagentStop` (`code.claude.com/docs/en/sub-agents`).
- ⚠️ **Критично:** per-agent frontmatter `hooks:` (а также `permissionMode`, `mcpServers`) **`Ignored for plugin subagents`**. Наши агенты — плагинные, значит per-agent хуки у них **не работают**. → **Кросс-агентный хук** (нужный и главному, и сабагентам) у хаба может жить **только в глобальном `plugin-dist/hooks/hooks.json`**. См. [agents.md §1.2.1](agents.md).

---

## 2. Hub usage

### 2.1. Текущие хуки в `export/hooks/`

| Файл | Event | Статус |
|---|---|---|
| `scan-suppression-markers.py` | `PostToolUse` (Edit\|Write\|MultiEdit) | LIVE через симлинк |
| `stop-gate-suppression-markers.py` | `Stop` | **STAGED** — не активирован, ждёт согласия пользователя |

### 2.2. Используемые vs неиспользуемые события

| Событие | Используем? | Если не — кандидат? |
|---|---|---|
| `PostToolUse` | да (scan-suppression-markers) | — |
| `Stop` | staged (stop-gate-suppression-markers) | — |
| `UserPromptSubmit` | нет | yes — блокировка опасных команд до отправки (по sub A) |
| `SubagentStart` | нет | yes — инъекция глобального контекста в каждый сабагент |
| `SessionStart`, `SessionEnd`, `PreToolUse`, `Notification`, `FileChanged`, `ConfigChange`, `PermissionRequest` | нет | maybe — конкретный usecase ещё не сформулирован |
| `PreCompact`, `PostCompact`, `Setup`, `PostToolUseFailure` | нет | maybe — payload неясен, нужна доп. проверка |

### 2.3. Принципы хаба для hook'ов

- **Абсолютные пути** в `"command"`: `$HOME/.claude/hooks/...` или `${CLAUDE_PROJECT_DIR}/...`, не относительные.
- **Fail-safe**: любая ошибка hook'а → exit 0 без output. Hook не должен ломать сессию.
- **Self-loop guard** для `Stop` hook'а: проверять `stop_hook_active` и exit 0.
- **Self-exclusion** для marker-detector hook'ов: `_SELF_FILES` whitelist, иначе детектор флагается сам собой.
- **Stdlib only** — без venv'ов и third-party deps для скорости старта.

---

## 3. Gray zones / open questions

1. **Полный список TypeScript SDK events** — упомянуто что TS поддерживает additional, список не выложен.
2. **Точный размер «brief delay»** file watcher'а — не задокументирован.
3. **Поведение symlinks** на `settings.json` для file watcher — empirically работает (хаб использует), но без формального smoke-теста.
4. **Payload schema для `Setup`, `PreCompact`, `PostCompact`, `SessionEnd`** — в найденных Context7-фрагментах не приведена явно. Требует доп. проверки перед использованием.
5. **Behavior `Stop` hook'а после 8 consecutive blocks** — override происходит автоматически. Что если hook нужно вызывать чаще? Workaround не описан.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/hooks` — payload schemas, decision-control.
- `code.claude.com/docs/en/hooks-guide` — patterns, examples, matchers.
- `code.claude.com/docs/en/agent-sdk/python` — `HookEvent` type list.
- `code.claude.com/docs/en/agent-sdk/typescript` — TS-specific types.

