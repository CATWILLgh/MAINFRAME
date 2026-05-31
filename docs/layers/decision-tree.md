# Decision tree: на какой слой ложится новый артефакт

> При появлении нового правила, навыка, проверки или процесса — **сначала пройди это дерево**, потом размещай. Без ad hoc выбора. Иначе хаб превратится в ком всего обо всем.

> Последнее обновление: 2026-05-29 (добавлена ось file-path match → Rule).

---

## Q1 — Как должно активироваться?

| Активация | Слой |
|---|---|
| Всегда, в каждой сессии каждого проекта | **CLAUDE.md** ([claude-md.md](claude-md.md)) |
| Claude читает файл по glob-паттерну (`Read` tool) | **Rule** ([rules.md](rules.md)) с `paths:` frontmatter |
| Семантический match (модель видит триггер и подключает) | **Skill** ([skills.md](skills.md)) |
| Системное событие (tool-use, stop, session-start, file change) | **Hook** ([hooks.md](hooks.md)) |
| Пользователь явно вызывает `/<name>` | **Command** ([commands.md](commands.md)) или Skill с `user-invocable: true` |
| Главный агент делегирует тяжёлую задачу | **Sub-agent** ([agents.md](agents.md)) |
| Технический гейт на команду / tool-вызов | **Permissions** ([permissions.md](permissions.md)) |
| Формат / стиль вывода | **Output style** ([output-styles.md](output-styles.md)) |

## Q2 — Где должен жить контекст?

| Цель | Механизм |
|---|---|
| В main context, всегда виден | CLAUDE.md или Skill (default) |
| В main context, только при триггере по path | Rule с `paths:` ([rules.md](rules.md)) |
| В main context, только при семантическом триггере | Skill с узким `when_to_use` |
| В отдельном forked context, summary возвращается | Skill `context: fork` **или** Sub-agent |
| Только в специальном sub-agent, main не видит вообще | Skill `disable-model-invocation: true` + Sub-agent `skills: [name]` |

## Q3 — Что это вообще?

| Природа | Слой |
|---|---|
| Always-on правило поведения, дисциплина | CLAUDE.md |
| Path-scoped knowledge (привязано к файлам по pattern) | Rule с `paths:` |
| Conditional knowledge / workflow / процедура (семантический trigger) | Skill |
| Реакция на событие в системе | Hook |
| Блокировка / разрешение конкретных команд | Permissions |
| Format / vibe / структура вывода | Output style |
| Изолированный worker (parallel/heavy) | Sub-agent |

## Q4 — Cross-layer triggering («переплетённая сетка»)

Без явного mechanism — silent reliance on hope. Не размещай артефакт без явной активации.

**Автоматические триггеры:**
- Hook — на системном событии.
- Rule с `paths:` — на Read файла по glob.
- Skill — на match по `description + when_to_use`.
- Sub-agent — на вызов `Agent(subagent_type)`.

**Явные cross-references (расширяют trigger surface):**
- Упоминание имени skill в CLAUDE.md → модель видит и оба frontmatter'а, и явную инструкцию.
- Упоминание имени skill в теле другого skill → relationship hint.
- `skills: [name]` в sub-agent frontmatter → preload при старте sub-agent'а.
- Skill упомянут в agent description → агент активирует его явно.

---

## Bloat-prevention toolkit

Каждый раз, когда добавляется новый артефакт, спроси: «может ли он раздувать main context во всех проектах?» Если да — применить один из:

1. **Rule с `paths:`** — если знание привязано к файлам по pattern (`.ts`, `migrations/**`), оно подгружается только когда Claude реально читает такой файл. См. [rules.md](rules.md).
2. **Узкий `when_to_use`** — skill не триггерится без необходимости.
3. **`disable-model-invocation: true`** на skill + `skills: [name]` в sub-agent — skill loaded ТОЛЬКО когда sub-agent активен. Main context чист.
4. **`context: fork`** — heavy skill отдельным контекстом; summary возвращается.
5. **Узкий `tools:` allowlist у sub-agent** — `Skill` не в tools = sub-agent совсем не подгружает skills.

---

## Recipe — типовые варианты

### Recipe A: глобальное правило поведения

> «Always be honest about severity» — действует везде, во всех проектах.

→ **CLAUDE.md (export/)**. Один bullet в соответствующей секции.

### Recipe B: дисциплинарный self-check

> «Перед declare-done скан-нуть файлы на TODO/FIXME» — должен срабатывать в конце задачи.

→ **Skill** (`user-invocable: false`, без `disable-model-invocation`). Триггер через `when_to_use`. Дополнительно — PostToolUse Hook для немедленного reminder per-edit.

### Recipe C: тяжёлый аудит конкретного домена

> «Проанализировать перформанс БД-запросов» — нужно несколько Explore-агентов, проверять docs, синтезировать.

→ **Sub-agent** (`perf-analyzer`) с preloaded skill (`perf-analysis`, `disable-model-invocation: true`). Main context не нагружается perf-знанием в нерелевантных проектах.

### Recipe D: технический гейт на опасную команду

> «Перехватить `git push --force`» — техническая защита.

→ **Permissions** (`deny` или `ask`, anywhere-form в deny, prefix-form в ask). НЕ skill, не CLAUDE.md — это техническая защита уровня tool-вызова.

### Recipe E: автоматический gate перед stop-турном

> «Перед declare-done — отказаться, если есть незарезолвленные маркеры».

→ **Hook** (`Stop` event, decision-control `block`). Не skill — это блокирующая реакция на event.

### Recipe F: user-вызываемая команда со сторонним эффектом

> «`/release` — собрать changelog и пометить теги».

→ **Command** или **Skill с `user-invocable: true`**. Side effects наружу → видимость в `/`-меню обязательна.

### Recipe G: path-scoped guidance, применимое глобально

> «При работе с `**/*.{ts,tsx}` напоминать про strict null-checks» — должно срабатывать только когда Claude реально читает TS-файл, в Python-проекте — не нагружать контекст.

→ **Rule** (`export/rules/<name>.md` → симлинк `~/.claude/rules/`) с `paths:` frontmatter. См. [rules.md](rules.md). Body короткий, English, project-agnostic globs.

---

## Что НЕ делать (при размещении)

- Не размещать «как обновлять decision tree» / «правила про правила». Дерево расширяется только когда реальный артефакт натыкается на ось, которую дерево не разрешает.
- Не делать skill там, где справится hook. Skill подключается контекстно (могут пропустить), hook срабатывает гарантированно.
- Не делать CLAUDE.md правило, если оно применимо только в одном домене (нарушает principle #1 агностичности).
- Не делать sub-agent там, где достаточно skill `context: fork` — agent тяжелее, имеет больше overhead.
- **Не делать Rule без `paths:` в хабе.** Rule без `paths:` грузится always-on во всех сессиях во всех проектах — это уже роль CLAUDE.md, дублирование. Если always-on — иди в CLAUDE.md.
- **Не делать Rule с глобами, привязанными к конкретному проекту** (`apps/myproject/**`). Хаб project-agnostic (§1); глобы должны быть pattern-based, не layout-based.

---

# Evolution: когда и как мигрировать существующее

Артефакты не статичны. Правило в CLAUDE.md может перерасти в skill + hook combo. Skill может разрастись и разделиться. Два skill'а — слиться. Эта секция даёт **наблюдаемые сигналы** для миграции и пошаговые правила; обе стороны (ты и я) должны видеть один и тот же сигнал и приходить к одному решению.

## §A. Observable migration signals (наблюдаемые триггеры)

Все сигналы — **наблюдаемые**, не «по ощущению». Если правило сформулировано как «когда выглядит большим» — оно не enforceable. Если сформулировано как «когда содержит conditional language» — обе стороны могут указать на файл и подтвердить факт.

> **Scope §A — только эволюция уже размещённого артефакта, не первичное размещение.** Эти сигналы отвечают на вопрос «когда мигрировать существующее правило/скилл», а не «куда поместить новое». Для первичного размещения используются Q1-Q4 + Recipe A-F выше. Прецедент ошибки: в ADR 0025 validation pass применил сигнал «conditional language → Recipe M1» к первичному размещению нового правила; source check скорректировал — conditional language в формулировке нового правила это **грамматика** condition-norm, не маркер процедуры.

| Сигнал (что наблюдается) | Где искать |
|---|---|
| Правило в CLAUDE.md содержит conditional language («когда X — делай Y», «в случае Z», «при триггере») | Грепом по `export/CLAUDE.md` |
| Правило в CLAUDE.md или skill'е содержит **path-specific language** (упоминает конкретные extensions, file patterns, directory layouts — `.ts`, `migrations/`, `.env`) и применимо только когда такой файл реально в работе | Grep по `export/CLAUDE.md` и `export/skills/**/SKILL.md` на extensions и pattern-keywords |
| SKILL.md превышает валидатор-лимит — body > 500 строк ИЛИ > 5K tokens | `validate-skill.py` report |
| SKILL.md покрывает 2+ темы (множественные `## ` секции с разными доменами) | Grep по headers в SKILL.md |
| Два skill'а имеют overlapping `when_to_use` фразы (одни и те же триггер-слова) | Сравнение frontmatter всех скиллов |
| Skill дублирует поведение существующего hook (та же проверка, та же reaction) | Sweep matching по labels/regex'ам |
| Domain-specific знание в always-on слое (`stack X`, `framework Y`, проектная специфика) | Принцип #1 хаба + grep по proper nouns |
| Hook output игнорируется моделью (модель не реагирует на `additionalContext`) | Эмпирика в сессиях |
| Combined `description + when_to_use` skill'а близок к лимиту (1536 chars) | `validate-skill.py` warning |
| ADR применил артефакт, и через 3+ итерации появились 2+ relate-ADR'а к нему | Подсчёт ссылок в `docs/decisions/` |

## §B. Migration recipes

Шаблонные миграции; пройдены те же 4 оси decision-tree, что и при первоначальном размещении.

### Recipe M1: CLAUDE.md правило → Skill (conditional decomposition)

**Триггер:** правило в CLAUDE.md содержит conditional language («когда X — делай Y»).

**Действие:**
1. Capability statement (что делать) → `description` нового skill.
2. Conditional часть (когда) → `when_to_use` нового skill.
3. Универсальная резюме-фраза остаётся в CLAUDE.md (одна строка), указывающая «details — в `<skill-name>`».
4. ADR с триггером + axis-walk + disposition.

### Recipe M2: Большой skill → Split (decomposition по темам)

**Триггер:** SKILL.md > 500 lines / 5K tokens, ИЛИ покрывает 2+ темы.

**Действие:**
1. Идентифицируй главные темы (по `## ` секциям).
2. Каждая тема → отдельный skill с собственными `description + when_to_use`.
3. Если есть always-on часть (одно правило для всех тем) — в CLAUDE.md одной строкой.
4. Старый skill: disposition по §C ниже.
5. ADR.

### Recipe M3: Два skill'а с overlapping triggers → Consolidate

**Триггер:** `when_to_use` двух скиллов содержит одни и те же триггер-фразы, либо они всегда вызываются вместе.

**Действие:**
1. Главный skill сохраняется (тот, чьё `description` шире).
2. Второй: либо merge содержимого в supporting file (`<main>/<second>.md`), либо delete с переносом уникального content.
3. ADR.

### Recipe M4: Skill дублирует automatic hook → Решить primary

**Триггер:** hook реализует ту же проверку/реакцию, что и skill.

**Действие:**
1. Если **гарантия исполнения важнее** контекстной видимости → hook остаётся primary; skill либо удаляется, либо становится human-readable reference (с пометкой «automated via `<hook>`»).
2. Если **контекстная активация важнее** (модель должна понимать почему срабатывает) → skill primary, hook опционален как fail-safe.
3. ADR.

### Recipe M5: Domain-specific знание из always-on → Sub-agent + scoped skill

**Триггер:** домен-специфичный контент в CLAUDE.md или широком skill (например, framework patterns, perf-procedures).

**Действие:**
1. Создать sub-agent (`export/agents/<domain>.md`) с `description` под domain.
2. Domain знание → skill с `disable-model-invocation: true`, чтобы main context не подхватывал.
3. В sub-agent frontmatter: `skills: [<domain-skill>]` — preload.
4. Удалить domain-фрагменты из CLAUDE.md / широкого skill.
5. ADR.

### Recipe M6: Heavy skill всегда нагружает main → `context: fork`

**Триггер:** skill реально полезен, но при auto-trigger вытаскивает много content в main context, который в основном остаётся неиспользованным.

**Действие:**
1. Skill frontmatter: `context: fork` + `agent: <тип>` (обычно `Explore`).
2. Возможно — переписать тело skill для использования `$ARGUMENTS`.
3. ADR.

### Recipe M7: Path-specific guidance в CLAUDE.md или skill → Rule с `paths:`

**Триггер:** правило в `export/CLAUDE.md` или скилле содержит path-specific language (см. сигнал в §A) — knowledge применимо только когда Claude реально работает с файлами по конкретному паттерну, а не во всех сессиях/задачах.

**Действие:**
1. Тело знания → новый файл `export/rules/<name>.md`.
2. Path-условие → `paths:` frontmatter с glob'ами; глобы должны быть project-agnostic (`**/*.ts`, не `apps/myproject/**`).
3. Проверить **anti-pattern over-broad glob** (см. [rules.md §2.1](rules.md)): если glob матчится почти в каждой сессии, миграция не оправдана — оставить в CLAUDE.md или skill.
4. Универсальная резюме-фраза остаётся в исходном файле (одна строка), указывает «details — в rule `<name>`», по аналогии с M1.
5. Disposition исходного фрагмента по §C (обычно `split` если CLAUDE.md содержал смешанное знание, либо `delete` если фрагмент целиком ушёл).
6. ADR.

**Когда НЕ применять M7:**
- Path-language есть, но glob будет матчиться почти всегда → over-broad, оставить в CLAUDE.md.
- Знание не «когда трогаешь файл X», а «когда выполняешь процедуру Y» — это семантический trigger, M1 (→ Skill), не M7.
- Знание уровня always-on safety (например, secrets handling) — путь Rule может его «спрятать», что снижает гарантию срабатывания. Оставить в CLAUDE.md.

## §C. Disposition старого артефакта

Четыре возможных финальных состояния. Это применение [ADR 0011 supersede-not-append](../decisions/0011-supersede-not-append.md) на уровне слоёв.

| Disposition | Когда применять | Что делать |
|---|---|---|
| **`delete`** | Контент полностью перенесён в новое место, дублёра не нужно | Удалить файл; обновить все ссылки (grep `<old-name>` по репо). |
| **`supersede with pointer`** | Файл живёт как tombstone-указатель на новое расположение | Заменить содержимое на 1-3 строки: «Superseded by `<new>`. See ADR `<NNNN>`.». Это валидный artifact, но не активный — индикатор истории. |
| **`split`** | Части ушли на разные слои/файлы | Каждый кусок move'ить отдельно по своему recipe. Старый файл — либо delete (если ничего не осталось), либо supersede with pointer (если есть ценная история). Все ссылки обновить. |
| **`augmentation-in-place`** | Артефакт корректен по сути, но требует усиления (явный label, carve-out, rationale enrichment, term substitution) **без перемещения** на другой слой | Edit текста в том же месте. Cross-refs стабильны (location и behaviour те же). В ADR — обязательно зафиксировать `trigger` (что побудило augmentation), `before` и `after` формулировки, `rationale` (почему изменение по сути а не косметика). |

**Правило: никогда не оставлять контрадикции рядом.** Если новый артефакт говорит X, а старый продолжает существовать с «not X» рядом — это шум, который путает обе стороны. Один из них должен победить, второй — disposition.

**Когда `augmentation-in-place`, а когда другая опция:**

| Случай | Disposition |
|---|---|
| Правило перемещается на другой слой (например, из CLAUDE.md → Skill) | **Migration recipe (M1-M6)**, не augmentation. См. §B. |
| Правило split на несколько правил на разных слоях | **`split`** |
| Правило полностью убирается (refuted / out-of-scope) | **`delete`** или **`supersede with pointer`** |
| Term substitution (нашли что текущий term has wrong public meaning) | **`augmentation-in-place`** |
| Добавление carve-out / exception к существующему правилу | **`augmentation-in-place`** |
| Усиление формулировки явным rationale (без изменения по сути) | **`augmentation-in-place`** |

**Прецеденты `augmentation-in-place`:**
- [ADR 0017](../decisions/0017-surgical-flag-adjacent.md) — retro source check добавил trivial carve-out.
- [ADR 0021](../decisions/0021-cargo-cult-and-fabrication.md) — term substitution (cargo-cult reuse) + rationale enrichment (documented LLM failure mode).

## §D. ADR mandatory

**Каждая миграция = ADR.** Это не bureaucracy — это audit trail для будущих сессий и компактов. Без ADR через 2 недели никто не вспомнит, почему правило ушло из CLAUDE.md в skill, и через ещё одну неделю кто-нибудь вернёт его обратно.

В ADR обязательно:
1. **Триггер** (какой observable signal из §A сработал).
2. **Axis-walk** (как прошли 4 оси decision-tree для нового расположения).
3. **Disposition** (delete / supersede / split — см. §C).
4. **Обновлённые ссылки** (список файлов с обновлёнными pointer'ами).
5. **Authoritative sources block** (см. §E ниже).

## §E. Authoritative source check before ADR

**Между классификацией кандидата и применением ADR — обязательный шаг для FRESH или PARTIAL кандидатов без двух+ независимых internal user-experience источников.** Этот шаг превращает «нам показалось, что это правильно» в «3-7 авторитетных источников подтверждают».

### Когда обязателен

| Статус кандидата | Источников | Check обязателен? |
|---|---|---|
| APPLIED | (уже зафиксировано) | нет |
| REJECT | (отклонено) | нет |
| OVERLAP | (дубль) | нет |
| BACKLOG | (отложено) | нет |
| FRESH или PARTIAL, **2+** независимых user-experience источников | OK | желательно, но не блокирующе |
| FRESH или PARTIAL, **1** источник user-experience | (рискованно) | **обязателен** |
| FRESH или PARTIAL, источник «best-practice-aligned» (без user-exp) | (слабее) | **обязателен** |

### Процедура

1. **Запустить research-сабагента** (sonnet, background) на authoritative external sources. Категории по природе правила:
   - **Anthropic Claude Code docs** (Context7 `/websites/code_claude`) — если правило про слой Claude Code.
   - **Engineering literature** — Google Engineering Practices, Linux Kernel guidelines, Martin Fowler, Refactoring, Clean Code — для behavioural rules.
   - **Security/Auth** — OWASP, CWE, RFC — для security.
   - **Performance** — official benchmarks, system docs — для perf.

2. **Sub-agent возвращает один из verdicts:**
   - **HOLDS** — правило согласуется с industry wisdom. Источники → в ADR секцию «Authoritative sources».
   - **NEEDS REFINEMENT** — нужны уточнения / carve-outs / context bounds. Corrigieren формулировку, повторить или применить.
   - **CONTRADICTS** — авторитеты говорят прямо обратное. Откатить или radically reformulate; зафиксировать в ADR причину.

3. **Применять ADR только после verdict.**

### Что в ADR

Раздел **«Authoritative sources»** (отдельно от internal sources):
- 3-7 источников с URL и verbatim quote (1-2 предложения).
- Знак влияния: `+1` (поддерживает), `-1` (антипод), `nuanced` (контекст-зависимо).
- Если verdict NEEDS REFINEMENT — явно отметить, что было изменено и почему.

### Прецеденты

- [ADR 0017 surgical-flag-adjacent](../decisions/0017-surgical-flag-adjacent.md) — retro-check после применения (первый случай). Verdict: HOLDS с refinement (trivial carve-out добавлен). С ADR 0018 и далее source check идёт **перед** apply, не после.

### Что check НЕ заменяет

- Decision-tree axis-walk (§A-§D) — остаётся обязательным.
- Анализ регрессий — остаётся.
- Validate hub'а (validate-claude-md.py, validate-skill.py) — остаётся.

Source check — это **дополнительный слой защиты от «уверенной галлюцинации»**: не «вместо», а «поверх».

## Sanity check для новой evolution-секции

Применяя эти правила к **ADR 0008 (severity-calibration)** обратным моделированием:
- В тот момент уже существовало правило honesty в CLAUDE.md.
- Сигнал, по §A: «правило содержит conditional language / обрастает rubric и discipline details».
- Recipe M1 (CLAUDE.md → Skill): capability «assign severity» + rubric + discipline → skill `severity-calibration`; универсальный принцип («reserve top level for real impact») остался в CLAUDE.md.
- Disposition (§C): не delete (одна строка осталась в CLAUDE.md), не split — это `extend` (выделение в skill при сохранении short pointer в CLAUDE.md). Этот вариант не покрыт явно — но укладывается в **M1 by design**: «универсальная резюме-фраза остаётся в CLAUDE.md».

→ Sanity check passed: применение новых правил привело бы к той же декомпозиции, что в ADR 0008. Mutual correction работает.
