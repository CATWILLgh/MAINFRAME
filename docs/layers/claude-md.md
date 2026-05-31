# Layer: CLAUDE.md (Operating instructions)

> Глобальная инструкция Claude, доставляемая в каждую сессию во всех проектах. В хабе: `export/CLAUDE.md` → симлинк `~/.claude/CLAUDE.md`.

> Последнее обновление: 2026-05-28 (3-секционный rewrite).

---

## Где живёт / Как install

- В хабе: `export/CLAUDE.md` (132 строки на 2026-05-28).
- На машине: `~/.claude/CLAUDE.md` (симлинк через `install.sh`).
- Действует во всех проектах через user-scope.
- File watcher Claude Code подхватывает правки без рестарта сессии.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Loading и scopes

Источник: `code.claude.com/docs/en/memory`.

Claude Code загружает CLAUDE.md с трёх уровней:
- **User-scope:** `~/.claude/CLAUDE.md` — действует во всех проектах одного пользователя.
- **Project-scope:** `<repo>/CLAUDE.md` — действует только в этом репо.
- **Local-scope (optional):** `<repo>/.claude/CLAUDE.md` — gitignored, локальные правки.

**Поведение при наличии нескольких:** project + local **дополняют** user-scope (accumulation), не override. User-scope — общий базовый слой.

### 1.2. Синтаксис

- Markdown без обязательного frontmatter.
- Структура произвольная; рекомендованные секции — `# Operating instructions`, далее тематические `## ...`.
- Имеет смысл сохранять короткие явные правила (bullets), а не длинные prose-блоки.

### 1.3. `@import` — импорт другого файла

> Синтаксис `@path/to/file.md` импортирует содержимое другого markdown-файла в этот же контекст.

Поддерживается:
- Относительные пути (`@docs/notes.md`, `@CHANGELOG.md` и т. п.).
- Глубина импортов ограничена (нет циклов).

### 1.4. Длина и adherence

> «Longer files reduce adherence» — официальная рекомендация Anthropic.

Жёсткого лимита нет; практический таргет — держать общий объём (user + project) меньше нескольких сотен строк, чтобы критические правила не утонули.

### 1.5. Что НЕ является CLAUDE.md

- `~/.claude/projects/<id>/CLAUDE.md` или похожее (если появится в будущем) — это **runtime state Claude Code**, накапливаемый в процессе работы, не часть хаба.

---

## 2. Hub usage

### 2.1. Текущий `export/CLAUDE.md`

Структура (на 2026-05-28, 132 строки):

| Секция | Что внутри |
|---|---|
| Partnership | Engineering partner, push back, surface tradeoffs |
| Communication | Plain language, brief, no fluff |
| Honesty | No fabrication, severity calibration |
| No flattery | Без оценочных открытий |
| Thinking and decision making | Anti-rationalization, step-by-step, lowest-risk |
| Evidence and sources | Context7 primary, authoritative web fallback |
| Verification | Empty-result re-query без фильтра |
| Output format | Concrete actionable, what/why/verify |
| Engineering practices | DRY/SOLID/KISS, no suppression markers, supersede-not-append, 400/60 file/fn limits |
| Problem-solving | Read 3-5 files; error-handling 5-step; do-not list (stop conditions, pre-flight) |
| Orchestration | Subagents для broad work |
| Advisor | Before substantive work / before declaring done |
| Git and commits | No Claude attribution |
| Destructive actions | Name explicitly, wait for ack |

### 2.2. Валидатор

[`tools/validate-claude-md.py`](../../tools/validate-claude-md.py) — проверяет Anthropic spec (R1-R5) + принцип агностичности (R6). Триггерится на `SessionStart` (summary) + `PostToolUse` (Edit/Write/MultiEdit; иначе exit instantly). Использует system `python3`, без зависимостей.

---

## 3. Gray zones / open questions

1. **Точный механизм rate-limiting / selective-загрузки секций** при длинном CLAUDE.md — не документирован Anthropic'ом. Эмпирически: краткие bullets адhere'ятся лучше длинных prose-блоков.
2. **Поведение `@import` при отсутствии файла** — не документировано. Не тестировали эмпирически.
3. **Project-scope CLAUDE.md в `<repo>/.claude/CLAUDE.md`** (если такая локация существует помимо `<repo>/CLAUDE.md`) — упоминаний не нашли в docs.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7):**
- `code.claude.com/docs/en/memory` — Claude Code memory mechanics, CLAUDE.md loading, `@import`.

**Internal:**
- `tools/validate-claude-md.py` — runtime валидатор.
