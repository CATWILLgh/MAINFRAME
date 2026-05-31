# Layer: Output styles

> Кастомные стили вывода Claude'а (например, «diagram-first», «code-reviewer», «brevity»). В хабе: `export/output-styles/<name>.md` (пока **пусто**).

> Последнее обновление: 2026-05-28 (3-секционный rewrite). Слой зарезервирован; артефактов нет.

---

## Где будет жить / Как install

- В хабе: `export/output-styles/<name>.md` — один файл на стиль.
- На машине: `~/.claude/output-styles/<name>.md` (симлинк через `install.sh`).
- Активация: через `/config` (выбор активного) или `outputStyle: "<name>"` в `settings.json`.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Frontmatter

Источник: `code.claude.com/docs/en/output-styles`.

```yaml
---
name: <kebab-case>                       # display name
description: <одна строка>               # для меню /config
keep-coding-instructions: <true|false>   # сохранять стандартные coding-инструкции при активации
---

Тело — markdown-инструкция, добавляется в system prompt при активации стиля.
```

### 1.2. Активация и scope

- Активный стиль выбирается через `/config` (runtime) или фиксируется глобально через `outputStyle: "<name>"` в `settings.json`.
- Стиль действует **на всю сессию**, пока не сменён.
- При активации тело файла **добавляется в system prompt** — модель видит инструкции как часть базовых правил.
- `keep-coding-instructions: false` — заменить стандартные coding-инструкции собственными; `true` (default) — добавить поверх.

### 1.3. Skills vs Output styles

| | Output style | Skill |
|---|---|---|
| Назначение | формат/тон/структура вывода (как отвечать) | conditional knowledge / workflow (что делать) |
| Активация | sticky через `/config` или settings (вся сессия) | per-trigger через `description + when_to_use` |
| В system prompt | да, при активации | нет; подгружается тело при триггере |
| Frontmatter | `name`, `description`, `keep-coding-instructions` | широкий (см. [skills.md](skills.md)) |

Output style — для **глобальной vibe сессии**. Skill — для **точечного знания/процедуры**.

---

## 2. Hub usage & ADRs

**Артефактов нет.** Слой зарезервирован. Возможные кандидаты на будущее:
- `code-review` — структурированный вывод для аудита.
- `brevity` — максимально короткие ответы.
- `diagram-first` — приоритет диаграмм/ASCII-схем.

Принципы хаба (когда появится первый стиль):
- **Один стиль = одна явная цель** (не «универсальный»).
- **`description` короткое** — показывается в `/config` меню.
- **Не дублировать поведение CLAUDE.md** — общие правила там; стиль покрывает только формат.

ADR'ы: нет.

---

## 3. Gray zones / open questions

1. **`keep-coding-instructions: false`** — что именно удаляется? Точный scope (только техническое поведение, или вся discipline) не описан явно.
2. **Composition** — можно ли активировать два стиля одновременно? Не задокументировано; предполагаемо нет.
3. **Persistence через сессии** — `outputStyle:` в settings sticky; через `/config` — на текущую сессию? Уточнить.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/output-styles` — формат, frontmatter, `keep-coding-instructions`.
- `code.claude.com/docs/en/agent-sdk/modifying-system-prompts` — как стили вписываются в system prompt.

**Internal:**
- [decision-tree.md](decision-tree.md) — Q3 (тип артефакта: vibe/format → Output style).
