# Слои хаба MAINFRAME

> Канонический список слоёв `export/` и навигатор по их спецификациям.
> Цель: единое понимание «что у нас точно есть, за что отвечает, как работает, чем обновлять» — без полуинтуитивных движений.

> **Статус:** активная reference. Создан 2026-05-28. Обновляется при появлении новой эмпирики, новых ADR'ов, новых authoritative-источников.

---

## Что считается «слоем»

Слой = тип артефакта в `export/`, который доставляется в `~/.claude/` через симлинк (`install.sh`) и действует во **всех** проектах пользователя без правок на стороне проекта.

**Не слои:**
- `docs/layers/` — спеки слоёв (то, что ты сейчас читаешь).
- `tools/` — скрипты, owned by хабом (валидаторы).

## Канонический список слоёв

| # | Слой | Где живёт | Что доставляется в `~/.claude/` | Спека |
|---|---|---|---|---|
| 1 | **CLAUDE.md** (operating instructions) | `export/CLAUDE.md` | `~/.claude/CLAUDE.md` (симлинк файла) | [claude-md.md](claude-md.md) |
| 2 | **Rules** (path-scoped) *(planned, пусто)* | `export/rules/<name>.md` | `~/.claude/rules/<name>.md` (симлинки) | [rules.md](rules.md) |
| 3 | **Skills** | `export/skills/<name>/` | `~/.claude/skills/<name>/` (симлинк папки) | [skills.md](skills.md) |
| 4 | **Hooks** | `export/hooks/*.py` + `export/settings.json` `hooks.*` | `~/.claude/hooks/*.py` (симлинки) + регистрация в settings | [hooks.md](hooks.md) |
| 5 | **Permissions** | `export/settings.json` `permissions.{allow,deny,ask}` | часть `~/.claude/settings.json` (симлинк целого файла) | [permissions.md](permissions.md) |
| 6 | **Settings** (прочие поля) | `export/settings.json` (всё кроме permissions/hooks) | часть `~/.claude/settings.json` | [settings.md](settings.md) |
| 7 | **Agents** *(planned, пусто)* | `export/agents/<name>.md` | `~/.claude/agents/<name>.md` (симлинки) | [agents.md](agents.md) |
| 8 | **Commands** *(planned, пусто)* | `export/commands/<name>.md` | `~/.claude/commands/<name>.md` (симлинки) | [commands.md](commands.md) |
| 9 | **Output styles** *(planned, пусто)* | `export/output-styles/<name>.md` | `~/.claude/output-styles/<name>.md` (симлинки) | [output-styles.md](output-styles.md) |

**Notes:**
- (4), (5) и (6) технически живут в одном файле (`settings.json`), но это **разные слои** — у них разные правила синтаксиса, разный eval, разные failure modes, разные источники истины. Спеки разнесены.
- (2), (7), (8), (9) — заранее зарезервированы; (2) Rules введён 2026-05-29 после empirical-верификации paths-activation; конкретных файлов в `export/rules/` пока нет — будут по мере выявления path-scoped guidance.
- Все симлинки создаются `install.sh` — покрывает все 8 слоёв с 2026-05-29. Использовать: `./install.sh` (sync), `./install.sh --dry-run` (диагностика), `./install.sh --uninstall` (снять симлинки).

## External touchpoints (не наши слои, но знать стоит)

| Touchpoint | Где живёт | Почему не слой |
|---|---|---|
| **MCP user-scope** | `~/.claude.json` (отдельный файл!) | Это не `~/.claude/settings.json`, и `.claude.json` хранит больше runtime-данных (credentials, история проектов). Симлинкать рискованно. Если решим — отдельным ADR. |
| **Runtime memory** | `~/.claude/projects/<id>/memory/` | Механика Claude Code — индекс + topic-файлы, накапливаются во время работы. Не доставляется хабом, это runtime state. |
| **Plugins marketplace** | community/official плагины через `enabledPlugins` | Мы используем (например, `context7=true`), но не создаём собственные плагины — это другая абстракция (плагин может содержать skills/agents/hooks/MCP внутри себя). Использовать готовое — да; создавать свой — отдельная задача. |
| **Project-scope artifacts** | `<repo>/.claude/` и `<repo>/.mcp.json` | Per-project, не глобальное. Хаб этого не касается. |

## Краткое объяснение MCP (Model Context Protocol)

MCP — стандарт от Anthropic, позволяющий Claude'у подключаться к внешним инструментам/данным (GitHub API, базы данных, Gmail, Context7 docs и т.п.). MCP-серверы регистрируются:
- **Project-scope:** `<repo>/.mcp.json` (для одного проекта).
- **User-scope:** `~/.claude.json` (для всех проектов).

Сейчас хаб не управляет `~/.claude.json` (это другой файл вне `~/.claude/`). Конкретные MCP-серверы (включая Context7, который мы используем) — подключены пользователем через `claude mcp add` либо настроены ранее. Если в будущем захотим стандартизировать набор user-scope MCP-серверов через хаб — оформим отдельным ADR.

## Decision tree — на какой слой ложится новый артефакт + как мигрировать существующий

При появлении нового правила/навыка/проверки/процесса — **сначала пройти [decision-tree.md](decision-tree.md)**, потом размещать. Без ad hoc выбора.

Дерево покрывает:
- **Placement (4 оси):** активация / изоляция контекста / тип артефакта / cross-layer triggering + bloat-prevention toolkit (`when_to_use`, `disable-model-invocation`, `context: fork`, узкий `tools:`).
- **Evolution (4 части):** observable migration signals → migration recipes → disposition старого артефакта (delete / supersede with pointer / split) → ADR mandatory с trigger + axis-walk + disposition.

## Формат каждой спеки

Целевая структура (после rewrite-итерации):

```
# <Layer name>

## Где живёт / Как install
(краткая ориентировка)

## 1. Canonical reference (из Anthropic docs) — 60-70%
   Дословные цитаты, schema, syntax, eval semantics, sources

## 2. Hub usage & ADRs — 20-30%
   Как мы применяем + ссылки на наши решения + side-by-side таблицы canonical vs hub где уместно

## 3. Gray zones / open questions — остаток
   Что не покрыто docs, наши гипотезы, известные runtime quirks
```

**Принцип naming:** «что работает» подкреплено либо authoritative-источником (Anthropic docs через Context7), либо empirical тестом (в текущей сессии или зафиксированном эксперименте). Без обоих — это не «работает», а «серая зона».

## Когда обновлять спеки

- Новая эмпирика (smoke-тест, поведение в реальной сессии) → дописать в соответствующую секцию с датой.
- Новый authoritative-источник (новая страница docs, прохождение через Context7) → обновить sources, при необходимости supersede прошлые гипотезы.
- ADR применил/изменил/откатил артефакт в слое → ссылка в «ADR'ы» соответствующего слоя.
- **Противоречие между прошлой записью и новой эмпирикой**: supersede (как в global engineering rule), не append.

## Известная серая зона по валидаторам и file watcher на симлинках

- ~~Точная процедура `install.sh`~~ — закрыто 2026-05-29.
- Validate matrix per layer — какой validator проверяет какой слой и при каком событии — open future work. Включает решение по `validate-rules.py`.
- Поведение симлинков `~/.claude/settings.json` → external file для file watcher — empirically работает (свежий settings.json подхватывается через симлинк без рестарта сессии), но без формальной проверки smoke-тестом.
