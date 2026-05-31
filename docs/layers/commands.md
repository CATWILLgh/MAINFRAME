# Layer: Commands

> Кастомные slash-команды (`/<name>`), явно вызываемые пользователем. В хабе: `export/commands/<name>.md` (пока **пусто**).

> Последнее обновление: 2026-05-28 (3-секционный rewrite). Слой зарезервирован; артефактов нет.

---

## Где будет жить / Как install

- В хабе: `export/commands/<name>.md` — один файл на команду.
- На машине: `~/.claude/commands/<name>.md` (симлинк через `install.sh`).
- Активация: после симлинка команда доступна как `/<name>` в чате.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Frontmatter

Источник: `code.claude.com/docs/en/slash-commands`.

```yaml
---
name: <kebab-case>                # display name; defaults к filename
description: <одна строка>        # для меню /-команд
allowed-tools: <subset>           # tools без permission ask
argument-hint: <[arg1] [arg2]>    # подсказка автокомплита
arguments: <space-separated или yaml-list>  # named positional для $name substitution
model: <opus|sonnet|haiku|inherit>          # override модели на ход
---

Тело — markdown-инструкция. `$ARGUMENTS` = всё после `/<name>`. Именованные args через `arguments:` mapping.
```

### 1.2. Отличие от Skill

| | Command | Skill |
|---|---|---|
| Активация | **только явный** `/<name>` пользователем | auto-trigger по `description + when_to_use` |
| Виден в `/`-меню | да (всегда) | если `user-invocable: true` |
| Frontmatter | `description`, `allowed-tools`, `arguments`, `argument-hint`, `model` | то же + `when_to_use`, `disable-model-invocation`, `context`, `effort` |
| Назначение | side-effect actions (commit, deploy, scaffold, release) | conditional knowledge / workflow |

Команда — для **обязательно-видимой пользователю** операции с эффектом наружу. Skill — для контекстно подключаемого знания/процедуры.

### 1.3. Активация

1. Пользователь печатает `/<name> <args>` в чате.
2. Claude видит frontmatter (description, argument-hint).
3. После вызова тело подгружается с подставленными аргументами.
4. Команды не auto-invoke'ятся моделью (это и есть отличие от skill).

### 1.4. Plugin namespacing

Команды внутри плагинов имеют префикс плагина (например, `/plugin:context7:query`). При прямом пользовательском хабе (без плагина) — без префикса.

---

## 2. Hub usage & ADRs

**Артефактов нет.** Слой зарезервирован. Кандидаты — см. backlog (например, `/release`, `/ticket`).

Принципы хаба (когда появится первая команда):
- **Команда = side-effect action**, иначе это skill.
- **Узкий `allowed-tools` allowlist** — команда делает только то, ради чего создана.
- **Описание `description` короткое** — оно показывается в `/`-меню, не место для tutorial.

ADR'ы: нет.

---

## 3. Gray zones / open questions

1. **Поведение `arguments:` mapping с YAML list vs space-separated string** — empirically не тестировали.
2. **Конфликт имён** — `/build` в хабе vs `/build` в плагине — кто побеждает? Не документировано явно.
3. **Параметры через `model:` override** — влияют только на ход команды или дольше? Уточнить при первом использовании.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/slash-commands` — формат, frontmatter, `$ARGUMENTS`.
- `code.claude.com/docs/en/features-overview` — Command vs Skill сравнение.

**Internal:**
- [decision-tree.md Recipe F](decision-tree.md) — когда выбирать command vs skill с `user-invocable: true`.
