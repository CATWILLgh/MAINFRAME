# Layer: Skills

> Опционально активируемые наборы инструкций. В хабе: `export/skills/<name>/SKILL.md` (+ supporting files) → симлинк `~/.claude/skills/<name>/`.

> Последнее обновление: 2026-05-28 (полный frontmatter spec + `disable-model-invocation`, `context: fork`).

---

## Где живёт / Как install

- В хабе: `export/skills/<name>/SKILL.md` (+ опциональные `<name>/*.md` supporting). Глубина строго = 1.
- На машине: `~/.claude/skills/<name>/` (симлинк на папку целиком).
- Активация: после симлинка скилл становится виден Claude'у через frontmatter «витрину».

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Полный frontmatter

Источник: `code.claude.com/docs/en/skills`, `code.claude.com/docs/en/slash-commands` (frontmatter reference).

```yaml
---
name: <kebab-case>                    # display name; defaults to dir name
description: <что делает>             # рекомендован; до 1024 chars
when_to_use: <когда триггерить>       # дополнительные триггер-фразы; appended to description
argument-hint: <[arg1] [arg2]>        # подсказка автокомплита
arguments: <space-separated или yaml-list>  # named positional args для $name substitution
disable-model-invocation: false       # true → Claude НЕ auto-loads skill + НЕ preloaded в sub-agents
user-invocable: true                  # false → скрыть из /-меню
allowed-tools: <subset списка tools>  # tools без permission ask
model: <model или 'inherit'>          # override модель на turn активации
effort: <low|medium|high|xhigh|max>   # override effort level
context: <main|fork>                  # fork → skill в forked context (изоляция)
agent: <тип>                          # с context: fork — какой агент форкнуть (например, Explore)
---
```

Combined `description + when_to_use` truncated at **1536 chars** (валидатор хаба следит).

### 1.2. Глубина и supporting files

- Скилл = папка `<name>/` с `SKILL.md` внутри.
- Опциональные supporting markdown в той же папке (`<name>/helper.md` и т.п.).
- **Глубина = 1**: вложенные подпапки не поддерживаются.
- Cross-skill `@import` не существует. Связи между скиллами — упоминание имени в теле; обе frontmatter видны в начале сессии.

### 1.3. Eval — когда модель подключает скилл

1. В начале сессии модель видит frontmatter всех симлинкованных скиллов (description + when_to_use).
2. При tool-use / тематическом запросе модель оценивает релевантность и подключает body, если match.
3. `user-invocable: true` → скилл в `/`-меню (пользователь может явно вызвать).
4. `user-invocable: false` → скрыт из меню, но **Claude всё равно auto-invoke по триггерам**.
5. `disable-model-invocation: true` → Claude НЕ auto-invoke. Активация только через явный `/<name>` (если user-invocable) или sub-agent `skills:` preload.

### 1.4. `context: fork` — skill в изолированном контексте

Skill с `context: fork` запускается в forked context (как sub-agent под капотом):
```yaml
---
name: deep-research
description: Research a topic thoroughly
context: fork
agent: Explore
---
Research $ARGUMENTS:
1. Find relevant files using Glob and Grep
...
```

Преимущество: skill не загружается в main context при auto-trigger; используется отдельный контекст, возвращается summary.

### 1.5. Skills vs Subagents — разделение зон

> «Skills are reusable content (instructions, knowledge, or workflows) that you can load into any context, adding to your main context window, and are best for reference material or invocable workflows.»
>
> «Subagents are isolated workers with their own context that run separately from your main conversation. They offer context isolation, use a separate context window... Use a subagent when you need context isolation or when your context window is getting full.»

Skill можно сделать ближе к sub-agent: `context: fork`. Sub-agent можно сделать ближе к skill: `skills:` preload. **Граница тонкая**; выбор — в [decision-tree.md](decision-tree.md).

---

## 2. Hub usage & ADRs

### 2.1. Текущие скиллы в `export/skills/`

| Имя | `user-invocable` | `disable-model-invocation` | Назначение |
|---|---|---|---|
| `no-suppression-markers` | false | (нет) — auto-loads | Self-discipline: не оставлять TODO/FIXME/skip/disable |
| `severity-calibration` | false | (нет) — auto-loads | Калибровка severity, rubric Critical/High/Medium/Low |
| `code-audit` | false | (нет) — auto-loads | Параллельный multi-aspect аудит через Explore |
| `surface-ticket` | false | (нет) — auto-loads | Формат тикета для out-of-scope находки в проекте; 5-state lifecycle + audit + reopen-в-том-же-файле |
| `ops-app-server-safety` | false | (нет) — auto-loads | Защита от дубликатов dev-серверов и Docker-стеков: preflight по порту/процессу, безопасный перезапуск через SIGTERM с эскалацией. Первый скилл без якоря в CLAUDE.md (чистый auto-loading) |

Все 5 скиллов активированы 2026-05-28 (раскат через `install.sh`).

**Все пять используют `description + when_to_use` split** (обновлено 2026-05-28) **в нейтральном стиле** (описываем триггер, не источник триггера). Combined chars в пределах валидатора (1536).

### 2.2. Лимиты валидатора хаба

[`tools/validate-skill.py`](../../tools/validate-skill.py) — runtime валидатор. Триггерится на `SessionStart` + `PostToolUse(Edit|Write|MultiEdit)`. Использует local `.venv` (tiktoken + pyyaml). Проверяет:

| Что | Лимит |
|---|---|
| SKILL.md body (без frontmatter) | 5K tokens / 500 lines |
| Supporting файл | 5K tokens / 60 lines |
| `description` | ≤ 1024 chars |
| `description + when_to_use` | ≤ 1536 chars |
| Глубина | ровно 1 |
| Dead supporting files | flagged |
| Required frontmatter | `name`, `description` (минимум) |

### 2.3. Принципы хаба для скиллов

- **Триггер-фразы — в `when_to_use`, не в `description`.** Description = что делает, when_to_use = когда сработать. После split 2026-05-28 у нас именно так.
- **Стиль формулировок — нейтральный, через ситуацию, без привязки к стороне** (2026-05-28). Описываем триггер, не источник триггера. Запрещены формулировки `"Use when the user asks..."`, `"Trigger when Claude is planning..."`. Правильно: `"Use when starting, restarting, or stopping a long-running development server or container stack."`. Причина — механика подключения сопоставляет *task* с *description*, не различая источник задачи (сообщение пользователя или собственный план модели). Условия применимости стиля: (а) конкретность — vague формулировки приводят к ложным срабатываниям; (б) сохранение якорных ключевых слов (команды типа `npm run dev`, имена процессов, глаголы действий).
- **`user-invocable: false` по умолчанию**, кроме случаев с side effects (commit, deploy, scaffold). Критерий = side effects, не invocation frequency.
- **`disable-model-invocation: true`** — использовать когда skill **не должен auto-load в main context**, а только preloaded в специальном sub-agent. Сейчас в хабе не применяется; запланировано для domain-skill'ов (`perf-analysis`).
- **Связь между скиллами** — через упоминание имени в теле (`severity-calibration` упомянут в `code-audit`).

---

## 3. Gray zones / open questions

1. **Условия активации скилла модель решает контекстно.** Известно (verified 2026-05-28 против `features-overview`): descriptions видны Claude'у в каждом запросе сессии, matching идёт по «task» (не только user message — также собственный план модели), конкретность бьёт расплывчатость, vague descriptions → ложные срабатывания. Точный алгоритм матча — не документирован.
2. **Конфликты between скиллами** при пересекающихся `when_to_use` — какой подключится первым? Не документировано.
3. **Token budget после compaction** — frontmatter остаётся в системе или подгружается заново? Не проверено.
4. **Sub-agent `skills:` preload в реальном runtime** — docs claim, не верифицировано empirically в этой сессии. Обязательная проверка при первом использовании (предыдущий опыт с permissions: docs и runtime расходятся).

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/skills` — формат, frontmatter, eval, `context: fork`.
- `code.claude.com/docs/en/slash-commands` — frontmatter reference (полный список полей).
- `code.claude.com/docs/en/plugins` — SKILL.md в плагинах.
- `code.claude.com/docs/en/features-overview` — Skill vs Subagent сравнение.
- `code.claude.com/docs/en/sub-agents` — `skills:` preload в sub-agents.

**Related:**
- `tools/validate-skill.py` — runtime валидатор.
- [decision-tree.md](decision-tree.md) — выбор слоя при появлении нового артефакта.
