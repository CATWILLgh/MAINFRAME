# Layer: Agents (sub-agents)

> Изолированные субагенты с собственным контекстом. В хабе: `export/agents/<name>.md` (пока **пусто** — зарезервированный слой).

> Последнее обновление: 2026-05-29 (research + дисциплина запуска).

---

## Где живёт

- В хабе: `export/agents/<name>.md` — один markdown-файл на агента.
- На машине: `~/.claude/agents/<name>.md` (симлинк файла, через [install.sh](../../install.sh)).
- Активация: после симлинка sub-agent вызывается через `Agent(subagent_type: "<name>")`.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Шесть режимов сабагентов — карта

Шесть режимов с разной context-inheritance и use case'ами.

| Режим | Activation | Context inherits | When |
|---|---|---|---|
| **A. Именованный** | `Agent(subagent_type=...)`, `@`-mention, `--agent` flag | Только task prompt + CLAUDE.md (если не Explore/Plan) | Изолированная focused задача |
| **B. Fork** | `CLAUDE_CODE_FORK_SUBAGENT=1` + `/fork` | **Весь parent transcript** | Параллельная ветка от текущего состояния |
| **C. Background** | `background: true` / `Ctrl+B` | Как A или B | Параллельная работа без блокировки |
| **D. SendMessage resume** | `SendMessage(to=agentId)`, требует `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | Свою прошлую историю | Продолжить остановленного субагента |
| **E. Agent teams** | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` + `TeamCreate` | CLAUDE.md проекта + spawn prompt; lead history не наследует | Несколько параллельных сессий с inter-agent communication |
| **F. Background sessions** | `claude --bg`, `/bg`, Agent View dispatch | Новая сессия → CLAUDE.md проекта; `/bg` из существующей → continue | Долгоживущие фоновые задачи, мониторинг |

### 1.2. Frontmatter — schema

Источник: `code.claude.com/docs/en/sub-agents` (file-based субагенты в Claude Code).

Базовые поля (наиболее часто используемые в хабе):

```yaml
---
name: <kebab-case>              # имя для Agent(subagent_type: "name")
description: <когда делегировать; видно main Claude'у>
prompt: <system prompt>         # либо тело файла после frontmatter, либо явное поле
tools: <Bash|Read|Write|...>    # allowlist subset стандартных tools.
                                # Без поля → inherit все parent tools (антипаттерн).
disallowedTools: <...>          # explicit block-list (camelCase per SDK schema).
                                # NB: kebab-case вариант (`disabled-tools`) встречается
                                # в part docs, но canonical SDK имя — camelCase.
model: <opus|sonnet|haiku|inherit>  # override модели. Default — inherit от parent.
skills:                         # preload skills в context субагента
  - skill-name-1
maxTurns: <N>                   # HARD CAP на API round-trips. Verified в
                                # AgentDefinition type (TS/Python SDK) + agent-loop
                                # docs документируют subtype `error_max_turns`
                                # как result когда лимит достигнут. [v2.1.128]
background: <true|false>        # форсит background mode (см. режим C).
permissionMode: <plan|acceptEdits|...>  # override permission mode.
                                # Нельзя расширить выше parent mode.
isolation: worktree             # форсить git worktree для file isolation.
---

Тело — system prompt субагента (если нет явного `prompt:`). `$ARGUMENTS` — placeholder для входных аргументов.
```

### 1.2.1. Полный frontmatter (документировано — `code.claude.com/docs/en/sub-agents`)

Раньше считалось, что семантика дополнительных полей (`hooks`, `mcpServers`, `memory`) «не описана explicitly» — это была gray zone. Теперь список полный и документированный:

| Поле | Назначение | Примечание |
|---|---|---|
| `name` | id агента (required) | Хуки получают это значение как `agent_type` |
| `description` | когда делегировать (required) | видно main Claude'у |
| `tools` | allowlist | **Опущено → наследует ВСЕ tools, включая `Skill`.** Указано → только перечисленные |
| `disallowedTools` | block-list | убрать tool из inherited/specified |
| `model` | `sonnet`/`opus`/`haiku`/full-id/`inherit` | default `inherit` |
| `maxTurns` | потолок agentic turns | soft enforcement (см. §3.1) |
| `skills` | preload | впрыскивает **полный контент** скилла в контекст на старте; ось «что preloaded», НЕ «что доступно» (доступ — через `tools`/`Skill`) |
| `permissionMode` | режим прав | ⚠️ **Ignored for plugin subagents** |
| `mcpServers` | MCP-серверы агента | ⚠️ **Ignored for plugin subagents** |
| `hooks` | lifecycle-хуки в области агента (все события; `Stop` → `SubagentStop`) | ⚠️ **Ignored for plugin subagents** |
| `memory` | `user`/`project`/`local` | кросс-сессионная память |

> ⚠️ **Критично для хаба:** наши агенты живут в `plugin-dist/` → это **plugin subagents**. Поля `permissionMode`, `mcpServers`, `hooks` в их frontmatter **игнорируются** (`code.claude.com/docs/en/sub-agents`, supported-frontmatter-fields). Следствие: задать хук / режим прав / MCP на уровне конкретного хаб-агента через frontmatter **нельзя** — работают только глобальные механизмы (`plugin-dist/hooks/hooks.json`, `export/settings.json`). Для кросс-агентного хука (нужного и главному агенту, и сабагентам) это и есть единственный путь — см. [hooks.md §1.6](hooks.md).

### 1.3. Agent tool — invocation schema

Атрибуты live в schema самого Agent tool (видны main Claude'у в каждой сессии):

| Атрибут | Назначение |
|---|---|
| `description` | Короткое (3-5 слов) описание задачи — попадает в UI и telemetry |
| `prompt` | Полный prompt сабагенту. На английском (см. §2.2.1) |
| `subagent_type` | Имя кастомного агента (из `export/agents/`) или built-in (Explore / Plan / general-purpose / claude-code-guide / statusline-setup) |
| `model` | Override модели per-call: `opus` / `sonnet` / `haiku`. Без поля — inherit |
| `isolation` | `"worktree"` — fresh git worktree (≈200–500 мс overhead + диск). Использовать только когда parallel agents мутируют файлы |
| `mode` | Override permission mode: `plan` / `acceptEdits` / `auto` / `default` / `dontAsk` / `bypassPermissions` |
| `run_in_background` | Запустить async — Claude получит notification при completion. Use когда не нужен результат для следующего хода |
| `team_name` | Для agent teams; иначе omit |
| `name` | Имя экземпляра для `SendMessage` resume |

### 1.4. Context isolation — что субагент видит / не видит

Полная картина — [subagent-modes-spec.md §4](../subagent-modes-spec.md). Короткий summary:

**Видит:**
- Свой system prompt (тело frontmatter-файла) или delegation prompt.
- `prompt` параметр от parent'а — **единственный канал** передачи контекста (для режимов A/C/E/F).
- CLAUDE.md hierarchy (кроме Explore и Plan, которые её пропускают).
- Preloaded skills из `skills:` frontmatter.
- Git status snapshot (кроме Explore и Plan).

**НЕ видит:**
- История разговора parent'а (исключение — Fork-субагент в B).
- Tool results parent'а.
- Skills, уже active в parent context (если их нет в `skills:` preload или не auto-loaded в субагенте).

**Возвращает:**
- Только final assistant message — это **есть** возвращаемое значение. Tool calls внутри субагента не surfaceятся в main context.

### 1.5. Built-in subagent types

| Тип | Модель | Tools | Особенности |
|---|---|---|---|
| `Explore` | Haiku | Read-only | **Skip'ает CLAUDE.md и git status.** Read excerpts (not whole files) с window'ом — для locate/grep задач |
| `Plan` | Inherits parent model | Read-only | **Skip'ает CLAUDE.md и git status.** Для design / plan reasoning без edit-капабилити |
| `general-purpose` | Inherits parent | All inherited | Универсальный worker. При fork mode заменяется fork-ом |
| `statusline-setup`, `claude-code-guide` | Specialized | — | Утилитарные, специфичные use cases |

### 1.6. Concurrency и lifetime caps

- **Per workflow concurrency**: `min(16, cpu_cores - 2)` concurrent agents (документировано в Workflow tool schema).
- **Per workflow lifetime**: 1000 agents total cap — backstop против runaway loops.
- **Nesting**: субагент **не может** spawn субагентов. Agent tool недоступен внутри субагента. Workflow внутри child Workflow throws.

---

## 2. Hub usage

### 2.1. Текущие агенты в `export/agents/`

| Агент | Назначение | Activation |
|---|---|---|
| `web-search` (model: sonnet, effort: low) | Поиск authoritative информации через Context7 + WebSearch/Fetch. Возвращает structured citations с verbatim quotes. Picked через 108-датапоинт tournament — 18/18 perfect runs, zero drift по 6 verification queries. | `Agent(subagent_type: "web-search")` |

Методология подбора model + effort для новых агентов — внутренний skill `agent-tournament` (project-scoped в MAINFRAME).

### 2.2. Subagent discipline (research 2026-05-29)

Дисциплина запуска субагентов выработана по research. Базовые правила вынесены в [export/CLAUDE.md](../../export/CLAUDE.md) Orchestration; детали — здесь.

#### 2.2.1. English prompts

Все subagent prompts — на английском, независимо от языка разговора с пользователем. Принцип хаба #3 + Anthropic prompt-engineering guidance (модели tuned на English, точнее следуют инструкциям, меньше токенов на ту же мысль). Применимо к `prompt:` параметру Agent tool, телу `export/agents/<name>.md`, prompts внутри Workflow. User-facing reply остаётся на языке пользователя.

#### 2.2.2. Anti-runaway

Surface — Claude Code CLI: main session + Agent tool invocation file-based субагентов из `~/.claude/agents/`. Verified hard knobs:

| Knob | Где | Эффект | Источник |
|---|---|---|---|
| `tools: [...]` allowlist | frontmatter | Структурно блокирует целые категории. Без `WebSearch` в allowlist — субагент физически не может искать. | sub-agents page |
| `maxTurns: N` | frontmatter | «Maximum number of agentic turns before the subagent stops» | sub-agents #supported-frontmatter-fields + tools-reference #agent-tool-behavior |
| `disallowedTools: [...]` | frontmatter | Block-list — убрать конкретный tool из inherited без полной enumeration. | sub-agents |
| `permissionMode: plan` | frontmatter | Read-only — субагент не сможет write. | sub-agents #permission-modes |
| `permissionMode: dontAsk` | frontmatter | Auto-deny prompts — субагент не получит permission escalation. | sub-agents |
| `background: true` | frontmatter | Auto-deny any tool call requiring prompt → cap blast radius. | sub-agents |
| `PreToolUse` hook с exit code 2 | внешний слой | Блокировка конкретных команд внутри allowed tool (e.g. allow Bash но reject SQL writes). | sub-agents #conditional-rules-with-hooks |

**5 tools структурно недоступны субагенту** независимо от frontmatter: `Agent` (no nesting), `AskUserQuestion`, `EnterPlanMode`, `ExitPlanMode` (unless `permissionMode: plan`), `ScheduleWakeup`, `WaitForMcpServers`. Источник: sub-agents #available-tools.

**Не documented:** timeout / parent abort mechanism для runaway. Единственное hard runtime termination — auto-compaction на ~95% context capacity.

Soft patterns (когда hard knobs не покрывают конкретный кейс):

Триада (без любого элемента pattern разваливается):

1. **Ordinal cap.** «Search at most 3 times» — конкретное число, не «try to limit».
2. **Output label.** «After your third search — return whatever you have and label BUDGET_EXHAUSTED.»
3. **Unconditional return clause.** «Whether or not you have an answer — return.»

Дополнительные patterns:
- **Consecutive empty abort.** «If 2 consecutive tool calls return empty/error — stop with label NO_PROGRESS.»
- **Output-format forcing early commit.** «After reading at most 5 files, write your analysis. Do not read more.»

**Anti-patterns:**
- Hedges: «try to limit», «aim for», «if possible», «prefer» — игнорируются.
- «Stop when you have enough information» — семантически пустое.
- Inherited tools без `tools:` allowlist — структурного cap нет.
- Prompt-only budget без structured return label — субагент извинится вместо отдачи partial data.

**Эмпирика 2026-05-29 (две итерации, 6 research-сабагентов с одинаковым template hard cap 5 tool calls):** 6/5, 5/5, 4/5, 4/5, 8/5, 6/5. Soft enforcement leaks ≈ 50% случаев, до +60% превышения. Когда критично — `maxTurns:` в frontmatter (verified hard knob).

#### 2.2.3. Output discipline

**Hard knob по структуре вывода в Claude Code CLI surface отсутствует.** Verified: ни поле frontmatter, ни Agent tool параметр для structured output / schema validation / retry-on-mismatch не documented. Возврат — natural-language summary, без contract. Источник: `code.claude.com/docs/en/sub-agents` — описание только «works independently and returns results», «relevant summary returns to your main conversation».

(`schema:` параметр Workflow tool — это Workflow-only, не Agent. Документированные example субагенты — code-reviewer, debugger — используют structured checklists в теле system prompt, но это illustrative, не documented best practice для machine-parseable.)

Soft patterns:
- **JSON-fenced + schema-in-prose** + «Return ONLY valid JSON matching this shape» — работает для Sonnet; для Haiku короче и без отвлечений.
- **Labeled-block** («OUTPUT:\n…») — parse только после метки, рассуждение до неё допустимо. Устойчивее, чем «no preamble».
- **Positive example beats negation** — конкретный sample вместо «do NOT include reasoning». Особенно для Opus 4.x.
- Короткий prompt + шаблон в конце — для Haiku.

**Anti-patterns:**
- «Return ONLY X» без позитивного якоря — soft, не надёжно.
- Markdown headers в prompt'е → воспроизводятся в выводе даже при «no headers».
- Ожидание structured output от Haiku на сложных задачах.

**Retry/parse pattern (когда строгая структура важна):**
1. `JSON.parse(result)` →
2. regex-extract первый JSON блок →
3. retry с явным example «previous returned malformed, return ONLY JSON» (1 retry max) →
4. degrade to prose-parse или бросить выше.

`SendMessage` для clarification требует `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — не применимо к одиночному Agent tool invocation.

#### 2.2.4. Composition decision criteria

Прямые documented patterns из `code.claude.com/docs/en/sub-agents`:

| Подход | Когда (по docs) |
|---|---|
| **Inline (main conversation)** | «frequent back-and-forth or iterative refinement», «multiple phases share significant context», «quick, targeted change», «latency matters» (subagents start fresh) |
| **Single Agent call** | Side task «would flood your main conversation with search results, logs, or file contents you won't reference again» — субагент работает в своём context, возвращает только summary |
| **Parallel research** | «spawn multiple subagents to work simultaneously» по independent areas. «Works best when the research paths don't depend on each other.» |
| **Chain (sequential)** | «find performance issues, then use the optimizer subagent to fix them» — main session passes output одного → input следующего |
| **Fork** | Когда named subagent «would need too much background to be useful» либо «try several approaches in parallel from the same starting point». Reuses parent prompt cache — дешевле named subagent для same-context задач |
| **Skill** | Когда нужен «reusable prompts or workflows that run in the main conversation context rather than isolated subagent context» |
| **`/btw`** | «quick question about something already in your conversation». Sees full context, no tool access, answer не добавляется в history |
| **Workflow tool** | На странице `sub-agents` **не описан**. Criterion Workflow vs manual parallel Agent calls в CLI docs отсутствует — эмпирическое правило хаба: Workflow при >5 workers или phase barriers. См. §3 gray zones |

**Built-in subagent выбор** (из `sub-agents` docs):
- `Explore` (Haiku, read-only) — «search or understand a codebase without making changes», «keeps exploration results out of your main conversation context».
- `general-purpose` — задача требует «both exploration and modification, complex reasoning to interpret results, or multiple dependent steps».

**Best practices (documented):**
- «Design focused subagents: each subagent should excel at one specific task».
- «Write detailed descriptions: Claude uses the description to decide when to delegate».
- «Limit tool access: grant only necessary permissions for security and focus».

**Cost warning (documented, implicit anti-pattern):**
- «Running many subagents that each return detailed results can consume significant context» — для sustained parallelism docs указывают на agent teams (каждый worker свой независимый context).
- «A fork cannot spawn further forks» — fork-of-fork невозможен.

**Эмпирические правила хаба** (не documented в CLI surface, по опыту):
- Параллельная ширина 2–3 для research/audit; 3–5 для component decomposition на больших codebase. >5 — диminishing synthesis value при linearly растущем token cost.
- Workflow vs manual fan-out — Workflow при >5 workers или явных phase barriers, manual Agent calls при 2–4 параллельных независимых задачах.
- Fan-out без independence (shared write target) — conflicting writes; всегда проверять что workers genuinely independent.

### 2.3. Хабовые принципы для агентов

Когда первый артефакт появится в `export/agents/`:

- **Узкий `tools:` allowlist** — agent делает только то, ради чего создан. Структурный cap > prompt cap.
- **Hard knobs обязательны.** Default convention для каждого `export/agents/<name>.md`: `tools:` allowlist (только нужные tools) + `maxTurns: N` (разумный потолок) + `permissionMode: plan` или `dontAsk` если нужно. Это **базовый минимум** для агента в хабе.
- **Soft patterns — дополнение, не замена.** Триаду (ordinal cap + label + unconditional return) в prompt включать как fallback и для специфики задачи, не как primary enforcement.
- **`model:` per task type** — sonnet/haiku по умолчанию; opus только если задача требует именно его силы.
- **`skills:` preload** для специализированных доменов — лучше, чем тащить domain knowledge в main CLAUDE.md.
- **`disable-model-invocation: true`** для domain skills — закрывает main context от лишней нагрузки. Связка: skill `disable-model-invocation: true` + sub-agent `skills: [name]`.
- **English body** (принцип #3).
- **Project-agnostic** (принцип #1) — agent не знает имена проектов, фреймворков как обязательных.
- **«Use proactively» в `description`** для агентов авто-диспатча. Anthropic CLI sub-agents docs явно рекомендуют фразу как механизм усиления автоматической делегации: «To encourage proactive delegation, include phrases like 'use proactively' in your subagent's description field» (`code.claude.com/docs/en/sub-agents`). Применяется к любому `export/agents/<name>.md`, чей intended-mode — автоматическое подключение по match'у description'а, не explicit user invocation.

---

## 3. Gray zones / open questions

1. **`maxTurns:` enforcement — мягкое.** Empirically verified через 108 invocations в tournament: `maxTurns: 10` нарушается частью вариантов (макс наблюдено 16 turns — haiku-low, до 1.6× cap). Среди sonnet+haiku × low/medium/high — только sonnet-medium дал 0/18 нарушений, остальные 1-2/18. Documented как «hard knob» в Anthropic spec, но runtime — partial enforcement. Не закладываться как структурная гарантия; рассматривать как soft target. Tool inheritance, deny patterns, `permissionMode` остаются основной защитой.
2. ✓ **RESOLVED (2026-06-01).** Полная frontmatter schema теперь документирована — см. §1.2.1. Ключевая находка: `permissionMode`, `mcpServers`, `hooks` **игнорируются для plugin subagents** (наши агенты именно такие). `disallowedTools` — canonical camelCase.
3. ✓ **RESOLVED (2026-06-01).** `skills:` preload верифицирован эмпирически этой сессией (`decision-reviewer`, `*-engineer` стартуют с preloaded скиллами и работают) + документирован: впрыскивает полный контент на старте, ось отдельная от доступа (`tools`/`Skill`). См. [skills.md §1.6](skills.md) и [[skill-triggering-mechanics]].
4. **Поведение `disable-model-invocation: true` skill при preload через sub-agent `skills:`** — корректно работает? Не верифицировано.
5. **Order разрешения tools** между sub-agent `tools:` allowlist и глобальными permissions (allow/deny/ask) — не явно описано.
6. **Workflow tool vs Agent tool пересечения** — Workflow обёртка над Agent с дополнительными primitives. Когда Workflow excess, когда необходим — рекомендация в §2.2.4 эмпирическая.

---

## Источники

**Authoritative (Anthropic Claude Code docs через Context7 + Agent tool live schema):**
- `code.claude.com/docs/en/sub-agents` — frontmatter (`maxTurns`, `tools`, `skills`, `model`), `--agents` JSON.
- `code.claude.com/docs/en/features-overview` — Skill vs Subagent сравнение; context isolation rationale.
- `code.claude.com/docs/en/agent-teams` — dimension decomposition pattern, inter-agent communication.
- `code.claude.com/docs/en/tools-reference` — tools inheritance default.
- Agent tool live schema (видна в каждой сессии) — 8 invocation attributes.
- Workflow tool live schema — concurrency caps `min(16, cpu_cores - 2)`, 1000-agent lifetime, `schema:` parameter, pipeline/parallel/phase primitives.

**Internal:**
- [docs/layers/decision-tree.md](decision-tree.md) — выбор слоя при появлении нового артефакта.
