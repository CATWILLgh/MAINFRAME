# Layer: CLAUDE.md (Operating instructions)

> Глобальная инструкция Claude, доставляемая в каждую сессию во всех проектах. В хабе: `export/CLAUDE.md` → симлинк `~/.claude/CLAUDE.md`.

> Последнее обновление: 2026-05-28 (3-секционный rewrite).

---

## Где живёт / Как install

- В хабе: `export/CLAUDE.md` (132 строки на 2026-05-28).
- На машине: `~/.claude/CLAUDE.md` (симлинк через `install.sh`, см. [ADR 0041](../decisions/0041-install-sh-extended-coverage.md)).
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
- Относительные пути (`@docs/principles.md`).
- Глубина импортов ограничена (нет циклов).

### 1.4. Длина и adherence

> «Longer files reduce adherence» — официальная рекомендация Anthropic.

Жёсткого лимита нет; практический таргет — держать общий объём (user + project) меньше нескольких сотен строк, чтобы критические правила не утонули.

### 1.5. Что НЕ является CLAUDE.md

- `~/.claude/projects/<id>/CLAUDE.md` или похожее (если появится в будущем) — это **runtime state Claude Code**, накапливаемый в процессе работы, не часть хаба. См. principle #4 в `docs/principles.md`.

---

## 2. Hub usage & ADRs

### 2.1. Текущий `export/CLAUDE.md`

Структура (на 2026-05-28, 132 строки):

| Секция | Что внутри | Источник правила |
|---|---|---|
| Partnership | Engineering partner, push back, surface tradeoffs | Принцип хаба |
| Communication | Plain language, brief, no fluff | Принцип хаба |
| Honesty | No fabrication, severity calibration | ADR 0008 |
| No flattery | Без оценочных открытий | Принцип |
| Thinking and decision making | Anti-rationalization, step-by-step, lowest-risk | ADR 0005 |
| Evidence and sources | Context7 primary, authoritative web fallback | Принцип |
| Verification | Empty-result re-query без фильтра | mining-B #3 |
| Output format | Concrete actionable, what/why/verify | Принцип |
| Engineering practices | DRY/SOLID/KISS, no suppression markers, supersede-not-append, 400/60 file/fn limits | ADR 0004, 0011 |
| Problem-solving | Read 3-5 files; error-handling 5-step; do-not list (stop conditions, pre-flight) | ADR 0006, 0007, 0010 |
| Orchestration | Subagents для broad work | Принцип |
| Advisor | Before substantive work / before declaring done | Принцип |
| Git and commits | No Claude attribution | Принцип |
| Destructive actions | Name explicitly, wait for ack | Принцип |

### 2.2. Валидатор

[`tools/validate-claude-md.py`](../../tools/validate-claude-md.py) — проверяет Anthropic spec (R1-R5) + принцип агностичности (R6). Триггерится на `SessionStart` (summary) + `PostToolUse` (Edit/Write/MultiEdit; иначе exit instantly). Использует system `python3`, без зависимостей.

### 2.3. ADR'ы

- [0004](../decisions/0004-suppression-markers-cross-layer.md) — suppression markers ban (cross-layer, не только CLAUDE.md).
- [0005](../decisions/0005-anti-rationalization.md) — anti-rationalization bullet в Thinking.
- [0006](../decisions/0006-stop-conditions.md) — stop-conditions в Problem-solving.
- [0007](../decisions/0007-pre-flight-situation-changed.md) — pre-flight check в Problem-solving.
- [0008](../decisions/0008-severity-calibration.md) — severity-calibration принцип в Honesty (+ staged skill).
- [0010](../decisions/0010-calibration-loop.md) — calibration loop в error-handling.
- [0011](../decisions/0011-supersede-not-append.md) — supersede-not-append в Engineering practices.

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
- `docs/rules-and-imports.md` — детальный разбор `@import` + `.claude/rules/` + связанные GitHub issues.
- `tools/validate-claude-md.py` — runtime валидатор.
