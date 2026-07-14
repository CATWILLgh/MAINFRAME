# Layer: Agents (sub-agents)

> **Staleness note (ADR 0085, 2026-07-08):** this spec describes the pre-neutral-core architecture, where files under `dist/claude-code/plugin/` / `dist/` are the source of truth. Sources are migrating to `core/` + `adapters/<tool>/`; `dist/claude-code/plugin/` and `dist/` remain the delivered, committed render targets. The spec is updated wave by wave as its layer lands on the core.


> Isolated subagents with their own context. In the hub: `dist/claude-code/plugin/agents/<name>.md` (7 agents), shipped via the `mainframe` plugin.

> Last updated: 2026-06-14 (plugin-migration actualization). Prior: 2026-05-29 (research + launch discipline).

---

## Where it lives

- In the hub: `dist/claude-code/plugin/agents/<name>.md` — one markdown file per agent.
- On the machine: delivered via the `mainframe` plugin (`dist/claude-code/plugin/` symlinked as one plugin), not an individual per-agent symlink.
- Activation: once the plugin is loaded, a sub-agent is invoked via `Agent(subagent_type: "<name>")`.

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Six subagent modes — map

Six modes with different context inheritance and use cases.

| Mode | Activation | Context inherits | When |
|---|---|---|---|
| **A. Named** | `Agent(subagent_type=...)`, `@`-mention, `--agent` flag | Task prompt + CLAUDE.md only (unless Explore/Plan) | Isolated, focused task |
| **B. Fork** | `CLAUDE_CODE_FORK_SUBAGENT=1` + `/fork` | **Full parent transcript** | Parallel branch from the current state |
| **C. Background** | `background: true` / `Ctrl+B` | Same as A or B | Parallel work without blocking |
| **D. SendMessage resume** | `SendMessage(to=agentId)`, requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | Its own past history | Resume a stopped subagent |
| **E. Agent teams** | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` + `TeamCreate` | Project CLAUDE.md + spawn prompt; lead history is not inherited | Multiple parallel sessions with inter-agent communication |
| **F. Background sessions** | `claude --bg`, `/bg`, Agent View dispatch | New session → project CLAUDE.md; `/bg` from existing → continue | Long-lived background tasks, monitoring |

### 1.2. Frontmatter — schema

Source: `code.claude.com/docs/en/sub-agents` (file-based subagents in Claude Code).

Core fields (most commonly used in the hub):

```yaml
---
name: <kebab-case>              # name for Agent(subagent_type: "name")
description: <when to delegate; visible to the main Claude>
prompt: <system prompt>         # either the file body after frontmatter, or an explicit field
tools: <Bash|Read|Write|...>    # allowlist subset of standard tools.
                                # Omitted → inherits ALL parent tools (anti-pattern).
disallowedTools: <...>          # explicit block-list (camelCase per SDK schema).
                                # NB: the kebab-case variant (`disabled-tools`) appears
                                # in some docs, but the canonical SDK name is camelCase.
model: <opus|sonnet|haiku|inherit>  # model override. Default — inherit from parent.
skills:                         # preload skills into the subagent context
  - skill-name-1
maxTurns: <N>                   # HARD CAP on API round-trips. Verified in
                                # AgentDefinition type (TS/Python SDK) + agent-loop
                                # docs document subtype `error_max_turns`
                                # as result when the limit is reached. [v2.1.128]
background: <true|false>        # forces background mode (see mode C).
permissionMode: <plan|acceptEdits|...>  # permission mode override.
                                # Cannot be elevated above parent mode.
isolation: worktree             # force git worktree for file isolation.
---

Body — system prompt of the subagent (if no explicit `prompt:`). `$ARGUMENTS` — placeholder for input arguments.
```

### 1.2.1. Full frontmatter (documented — `code.claude.com/docs/en/sub-agents`)

Previously it was assumed that the semantics of additional fields (`hooks`, `mcpServers`, `memory`) were "not described explicitly" — this was a gray zone. The list is now complete and documented:

| Field | Purpose | Note |
|---|---|---|
| `name` | agent id (required) | Hooks receive this value as `agent_type` |
| `description` | when to delegate (required) | visible to the main Claude |
| `tools` | allowlist | **Omitted → inherits ALL tools, including `Skill`.** Specified → only those listed |
| `disallowedTools` | block-list | remove a tool from inherited/specified |
| `model` | `sonnet`/`opus`/`haiku`/full-id/`inherit` | default `inherit` |
| `maxTurns` | ceiling on agentic turns | soft enforcement (see §3.1) |
| `skills` | preload | injects the **full content** of the skill into context at startup; the "what is preloaded" axis, NOT "what is accessible" (access is via `tools`/`Skill`) |
| `permissionMode` | permission mode | ⚠️ **Ignored for plugin subagents** |
| `mcpServers` | MCP servers for the agent | ⚠️ **Ignored for plugin subagents** |
| `hooks` | lifecycle hooks in the agent scope (all events; `Stop` → `SubagentStop`) | ⚠️ **Ignored for plugin subagents** |
| `memory` | `user`/`project`/`local` | cross-session memory |

> ⚠️ **Critical for the hub:** our agents live in `dist/claude-code/plugin/` → they are **plugin subagents**. The fields `permissionMode`, `mcpServers`, `hooks` in their frontmatter **are ignored** (`code.claude.com/docs/en/sub-agents`, supported-frontmatter-fields). Consequence: setting a hook / permission mode / MCP for a specific hub agent via frontmatter **is not possible** — only global mechanisms work (`dist/claude-code/plugin/hooks/hooks.json`, `dist/claude-code/settings.json`). For a cross-agent hook (needed by both the main agent and subagents) this is the only path — see [hooks.md §1.6](hooks.md).

### 1.3. Agent tool — invocation schema

Attributes live in the schema of the Agent tool itself (visible to the main Claude in every session):

| Attribute | Purpose |
|---|---|
| `description` | Short (3-5 words) task description — appears in UI and telemetry |
| `prompt` | Full prompt to the subagent. In English (see §2.2.1) |
| `subagent_type` | Name of a custom agent (from `dist/claude-code/plugin/agents/`) or built-in (Explore / Plan / general-purpose / claude-code-guide / statusline-setup) |
| `model` | Model override per-call: `opus` / `sonnet` / `haiku`. Without the field — inherit |
| `isolation` | `"worktree"` — fresh git worktree (≈200–500 ms overhead + disk). Use only when parallel agents mutate files |
| `mode` | Permission mode override: `plan` / `acceptEdits` / `auto` / `default` / `dontAsk` / `bypassPermissions` |
| `run_in_background` | Launch async — Claude receives a notification on completion. Use when the result is not needed for the next turn |
| `team_name` | For agent teams; otherwise omit |
| `name` | Instance name for `SendMessage` resume |

### 1.4. Context isolation — what a subagent sees / does not see

Full picture — [subagent-modes-spec.md §4](../subagent-modes-spec.md). Short summary:

**Sees:**
- Its own system prompt (frontmatter file body) or delegation prompt.
- The `prompt` parameter from the parent — **the only channel** for passing context (for modes A/C/E/F).
- The **full** CLAUDE.md memory hierarchy the main session loads — managed-policy + **user-global `~/.claude/CLAUDE.md`** + project `./CLAUDE.md` + `CLAUDE.local.md`. Named custom/plugin subagents are NOT scoped to project-only; the user-global file (the hub's `dist/claude-code/CLAUDE.md`) IS loaded into them. Explore and Plan are the only two that skip CLAUDE.md (and git status), with no frontmatter knob to change that. So an agent body may rely on the umbrella CLAUDE.md being present — but the markdown link to it is human navigation only; the content arrives as loaded memory, not via the link. Source: the `sub-agents` doc ("Explore and Plan are the only subagents that omit CLAUDE.md and git status") + the `memory` doc, corroborated by claude-code-guide (which reports an in-CLI check — relayed, not witnessed here). Checked 2026-06-15.
- Preloaded skills from `skills:` frontmatter.
- Git status snapshot (except Explore and Plan).

**Does NOT see:**
- Parent conversation history (exception — Fork subagent in B).
- Parent tool results.
- Skills already active in the parent context (unless present in `skills:` preload or auto-loaded in the subagent).

**Returns:**
- Only the final assistant message — this **is** the return value. Tool calls inside a subagent are not surfaced in the main context.

### 1.5. Built-in subagent types

| Type | Model | Tools | Notes |
|---|---|---|---|
| `Explore` | Haiku | Read-only | **Skips CLAUDE.md and git status.** Reads excerpts (not whole files) with a window — for locate/grep tasks |
| `Plan` | Inherits parent model | Read-only | **Skips CLAUDE.md and git status.** For design / plan reasoning without edit capability |
| `general-purpose` | Inherits parent | All inherited | Universal worker. In fork mode, replaced by a fork |
| `statusline-setup`, `claude-code-guide` | Specialized | — | Utility, specific use cases |

### 1.6. Concurrency and lifetime caps

- **Per workflow concurrency**: `min(16, cpu_cores - 2)` concurrent agents (documented in Workflow tool schema).
- **Per workflow lifetime**: 1000 agents total cap — backstop against runaway loops.
- **Nesting**: since CLI **2.1.172** (2026-06-10) a subagent **can** spawn subagents, up to **5 levels** deep (per the CHANGELOG entry, relayed by claude-code-guide + web-search reading that same line; the exact depth is relayed, not runtime-probed). Before 2.1.172, nesting was blocked — `Agent` / `Task` silently filtered inside a subagent (issue #61993). Gating: an agent whose `tools:` omits `Agent` still cannot spawn, by design (inferred from the same allowlist mechanism verified for `Skill` this session) — e.g. the hub's narrow-tools `*-engineer` agents. Two adjacent mechanisms keep tighter limits, do not conflate: a **Workflow** inside a child Workflow throws (1 level); **agent-teams** teammates cannot spawn teams/teammates (only the lead manages the team). Checked 2026-06-15.

---

## 2. Hub usage

### 2.1. Current agents in `dist/claude-code/plugin/agents/`

7 agents as of 2026-06-14, shipped via the `mainframe` plugin.

| Agent | Purpose | Activation |
|---|---|---|
| `decision-reviewer` | Independent, evidence-grounded review of a proposed decision / design / approach before it is locked in (architecture, high cost-of-wrong). Read-only. | `Agent(subagent_type: "decision-reviewer")`; also `task-workflow` step 6a |
| `devops-engineer` | Deployment / infra / ops — Docker Compose, CI/CD, Dockerfiles, managed DBs, domains/TLS, secrets, observability; drives Dokploy via the `dokploy-api` skill. Write-capable, background. | auto-dispatch on a deploy / infra task |
| `python-backend-engineer` | Python backend (FastAPI / Django / Flask + ORM) via the `python-backend-patterns` skill. Write-capable. | auto-dispatch on a Python backend task |
| `nestjs-backend-engineer` | Node / TS backend (NestJS / Express / Fastify) via `nestjs-backend-patterns`. Write-capable. | auto-dispatch |
| `nextjs-backend-engineer` | Next.js App Router backend (Route Handlers, Server Actions, RSC) via `nextjs-backend-patterns`. Write-capable. | auto-dispatch |
| `react-frontend-engineer` | React / Vite SPA frontend via `react-frontend-patterns` (+ `shadcn`, `frontend-design`). Write-capable. | auto-dispatch |
| `web-search` (model: sonnet, effort: low) | Authoritative info via Context7 + WebSearch/Fetch; structured citations with verbatim quotes. Tournament-selected — 18/18 perfect runs, zero drift across 6 verification queries. | `Agent(subagent_type: "web-search")` |

Methodology for selecting model + effort for new agents — internal skill `agent-tournament` (project-scoped in MAINFRAME).

### 2.2. Subagent discipline (research 2026-05-29)

Subagent launch discipline was developed through research. Basic rules are in [dist/claude-code/CLAUDE.md](../../dist/claude-code/CLAUDE.md) Orchestration; details here.

#### 2.2.1. English prompts

All subagent prompts are in English, regardless of the language of the conversation with the user. Hub principle #3 + Anthropic prompt-engineering guidance (models are tuned on English, follow instructions more precisely, fewer tokens for the same content). Applies to the `prompt:` parameter of the Agent tool, the body of `dist/claude-code/plugin/agents/<name>.md`, and prompts inside Workflow. User-facing replies remain in the user's language.

#### 2.2.2. Anti-runaway

Surface — Claude Code CLI: main session + Agent tool invocation of file-based subagents from `~/.claude/agents/`. Verified hard knobs:

| Knob | Where | Effect | Source |
|---|---|---|---|
| `tools: [...]` allowlist | frontmatter | Structurally blocks entire categories. Without `WebSearch` in the allowlist — the subagent physically cannot search. | sub-agents page |
| `maxTurns: N` | frontmatter | "Maximum number of agentic turns before the subagent stops" | sub-agents #supported-frontmatter-fields + tools-reference #agent-tool-behavior |
| `disallowedTools: [...]` | frontmatter | Block-list — remove a specific tool from inherited without full enumeration. | sub-agents |
| `permissionMode: plan` | frontmatter | Read-only — the subagent cannot write. | sub-agents #permission-modes |
| `permissionMode: dontAsk` | frontmatter | Auto-deny prompts — the subagent does not receive permission escalation. | sub-agents |
| `background: true` | frontmatter | Auto-deny any tool call requiring a prompt → cap blast radius. | sub-agents |
| `PreToolUse` hook with exit code 2 | external layer | Block specific commands inside an allowed tool (e.g. allow Bash but reject SQL writes). | sub-agents #conditional-rules-with-hooks |

**5 tools are structurally unavailable to a subagent** regardless of frontmatter: `AskUserQuestion`, `EnterPlanMode`, `ExitPlanMode` (unless `permissionMode: plan`), `ScheduleWakeup`, `WaitForMcpServers`. Source: sub-agents #available-tools. (`Agent` is NOT in this list: subagent nesting works since CLI 2.1.172 and is gated by the `tools:` allowlist, not structurally blocked — see §1.6.)

**Not documented:** timeout / parent abort mechanism for runaway. The only hard runtime termination — auto-compaction at ~95% context capacity.

Soft patterns (when hard knobs do not cover a specific case):

The triad (without any element the pattern falls apart):

1. **Ordinal cap.** "Search at most 3 times" — a concrete number, not "try to limit".
2. **Output label.** "After your third search — return whatever you have and label BUDGET_EXHAUSTED."
3. **Unconditional return clause.** "Whether or not you have an answer — return."

Additional patterns:
- **Consecutive empty abort.** "If 2 consecutive tool calls return empty/error — stop with label NO_PROGRESS."
- **Output-format forcing early commit.** "After reading at most 5 files, write your analysis. Do not read more."

**Anti-patterns:**
- Hedges: "try to limit", "aim for", "if possible", "prefer" — are ignored.
- "Stop when you have enough information" — semantically empty.
- Inherited tools without a `tools:` allowlist — no structural cap.
- Prompt-only budget without a structured return label — the subagent will apologize instead of returning partial data.

**Empirics 2026-05-29 (two iterations, 6 research subagents with identical template hard cap of 5 tool calls):** 6/5, 5/5, 4/5, 4/5, 8/5, 6/5. Soft enforcement leaks in ≈50% of cases, up to +60% overage. **Read this the right way (revised 2026-06-02):** the cap of 5 was itself too tight — a leash, not a backstop. Under-provisioning starves the task: it returns holes, or `maxTurns` cuts it off mid-work. The cap is a runaway backstop set *generously above* the expected work; the prompt triad (label + unconditional return) is what makes a hit cap degrade to partial output instead of silence. For write-capable multi-step agents, omit `maxTurns` entirely and fence by `tools:` + scope (a low cap terminates them mid-task — soft means imprecise, not absent).

#### 2.2.3. Output discipline

**There is no hard knob for output structure in the Claude Code CLI surface.** Verified: neither a frontmatter field nor an Agent tool parameter for structured output / schema validation / retry-on-mismatch is documented. The return is a natural-language summary, without a contract. Source: `code.claude.com/docs/en/sub-agents` — describes only "works independently and returns results", "relevant summary returns to your main conversation".

(`schema:` parameter of the Workflow tool — this is Workflow-only, not Agent. The documented example subagents — code-reviewer, debugger — use structured checklists in the system prompt body, but this is illustrative, not a documented best practice for machine-parseable output.)

Soft patterns:
- **JSON-fenced + schema-in-prose** + "Return ONLY valid JSON matching this shape" — works for Sonnet; for Haiku, keep it shorter and without distractions.
- **Labeled-block** ("OUTPUT:\n…") — parse only after the label, reasoning before it is acceptable. More robust than "no preamble".
- **Positive example beats negation** — a concrete sample instead of "do NOT include reasoning". Especially for Opus 4.x.
- Short prompt + template at the end — for Haiku.

**Anti-patterns:**
- "Return ONLY X" without a positive anchor — soft, not reliable.
- Markdown headers in the prompt → reproduced in output even with "no headers".
- Expecting structured output from Haiku on complex tasks.

**Retry/parse pattern (when strict structure matters):**
1. `JSON.parse(result)` →
2. regex-extract first JSON block →
3. retry with explicit example "previous returned malformed, return ONLY JSON" (1 retry max) →
4. degrade to prose-parse or throw upstream.

`SendMessage` for clarification requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — not applicable to a single Agent tool invocation.

#### 2.2.4. Composition decision criteria

Direct documented patterns from `code.claude.com/docs/en/sub-agents`:

| Approach | When (per docs) |
|---|---|
| **Inline (main conversation)** | "frequent back-and-forth or iterative refinement", "multiple phases share significant context", "quick, targeted change", "latency matters" (subagents start fresh) |
| **Single Agent call** | Side task "would flood your main conversation with search results, logs, or file contents you won't reference again" — the subagent works in its own context, returns only a summary |
| **Parallel research** | "spawn multiple subagents to work simultaneously" across independent areas. "Works best when the research paths don't depend on each other." |
| **Chain (sequential)** | "find performance issues, then use the optimizer subagent to fix them" — main session passes output of one → input of the next |
| **Fork** | When a named subagent "would need too much background to be useful" or to "try several approaches in parallel from the same starting point". Reuses parent prompt cache — cheaper than a named subagent for same-context tasks |
| **Skill** | When "reusable prompts or workflows that run in the main conversation context rather than isolated subagent context" are needed |
| **`/btw`** | "quick question about something already in your conversation". Sees full context, no tool access, answer is not added to history |
| **Workflow tool** | Not described on the `sub-agents` page. The criterion for Workflow vs manual parallel Agent calls is absent from CLI docs — hub empirical rule: Workflow for >5 workers or phase barriers. See §3 gray zones |

**Built-in subagent selection** (from `sub-agents` docs):
- `Explore` (Haiku, read-only) — "search or understand a codebase without making changes", "keeps exploration results out of your main conversation context".
- `general-purpose` — task requires "both exploration and modification, complex reasoning to interpret results, or multiple dependent steps".

**Best practices (documented):**
- "Design focused subagents: each subagent should excel at one specific task".
- "Write detailed descriptions: Claude uses the description to decide when to delegate".
- "Limit tool access: grant only necessary permissions for security and focus".

**Cost warning (documented, implicit anti-pattern):**
- "Running many subagents that each return detailed results can consume significant context" — for sustained parallelism, docs point to agent teams (each worker has its own independent context).
- "A fork cannot spawn further forks" — fork-of-fork is not possible.

**Hub empirical rules** (not documented in the CLI surface, based on experience):
- Parallel width of 2–3 for research/audit; 3–5 for component decomposition on large codebases. >5 — diminishing synthesis value at linearly growing token cost.
- Workflow vs manual fan-out — Workflow for >5 workers or explicit phase barriers, manual Agent calls for 2–4 parallel independent tasks.
- Fan-out without independence (shared write target) — conflicting writes; always verify that workers are genuinely independent.

### 2.3. Hub principles for agents

Convention for every `dist/claude-code/plugin/agents/<name>.md`:

- **Narrow `tools:` allowlist** — the agent does only what it was created for. Structural cap > prompt cap.
- **The `tools:` allowlist is the mandatory hard knob.** Default convention for every `dist/claude-code/plugin/agents/<name>.md`: `tools:` allowlist (only needed tools), plus `permissionMode: plan` / `dontAsk` if needed. It is the baseline minimum and the primary scope guard. `maxTurns` is NOT a default — it is a runaway backstop for genuinely open-ended workers, set generously above the expected turn count; **omit it on write-capable multi-step agents** (a low cap terminates them mid-task — see §3.1). Precedent: the engineer agents had `maxTurns` removed after it killed them mid-task.
- **Soft patterns — supplement, not replacement.** Include the triad (ordinal cap + label + unconditional return) in the prompt as a fallback and for task specifics, not as primary enforcement.
- **`model:` per task type** — sonnet/haiku by default; opus only if the task genuinely requires its capabilities.
- **`skills:` preload** for specialized domains — better than pulling domain knowledge into the main CLAUDE.md.
- **`disable-model-invocation: true`** for domain skills — keeps the main context free of unnecessary load. Pattern: skill `disable-model-invocation: true` + sub-agent `skills: [name]`.
- **English body** (principle #3).
- **Project-agnostic** (principle #1) — the agent does not know project names or frameworks as mandatory.
- **"Use proactively" in `description`** for auto-dispatch agents. Anthropic CLI sub-agents docs explicitly recommend the phrase as a mechanism to strengthen automatic delegation: "To encourage proactive delegation, include phrases like 'use proactively' in your subagent's description field" (`code.claude.com/docs/en/sub-agents`). Applies to any `dist/claude-code/plugin/agents/<name>.md` whose intended mode is automatic activation on description match, not explicit user invocation.

---

## 3. Gray zones / open questions

1. **`maxTurns:` enforcement — soft.** Empirically verified across 108 invocations in tournament: `maxTurns: 10` is violated by some variants (max observed 16 turns — haiku-low, up to 1.6× cap). Among sonnet+haiku × low/medium/high — only sonnet-medium gave 0/18 violations, the rest 1-2/18. Documented as a "hard knob" in Anthropic spec, but runtime is partial enforcement. Do not rely on it as a structural guarantee; treat as a soft target. Tool inheritance, deny patterns, `permissionMode` remain the primary protection. **Soft means imprecise, not absent:** the cap still fires, just later than N — so a low cap still cuts a long task off mid-work (the starvation failure mode), while a generous cap rarely binds. NB surface: the agent-SDK `agent-loop` docs describe a cleaner `max_turns` (counts tool-use turns; `error_max_turns` + session resume on hit) — that is the **SDK** surface, not the **CLI** file-based-agent surface this hub targets; the soft-enforcement finding above is the CLI reality.
2. ✓ **RESOLVED (2026-06-01).** Full frontmatter schema is now documented — see §1.2.1. Key finding: `permissionMode`, `mcpServers`, `hooks` **are ignored for plugin subagents** (our agents are exactly that). `disallowedTools` — canonical camelCase.
3. ✓ **RESOLVED (2026-06-01).** `skills:` preload verified empirically in this session (`decision-reviewer`, `*-engineer` start with preloaded skills and work) + documented: injects full content at startup, a separate axis from access (`tools`/`Skill`). See [skills.md §1.6](skills.md) and [[skill-triggering-mechanics]].
4. ✓ **RESOLVED (2026-06-02).** `disable-model-invocation: true` and a sub-agent `skills:` binding compose correctly — **verified by a realistic probe**: dispatch `devops-engineer`, ask a Dokploy question, let it work normally. The agent located its `dokploy-api` skill, **read** the files, and answered correctly (`x-api-key` not `Authorization`, the `/api` prefix, bare-JSON responses), while a fresh **main** session did NOT auto-load the skill and routed to the agent. So bloat-prevention #3 works: hidden from main, usable by the agent. **Mechanism nuance (corrects §1.2.1's "injects full content"):** `skills:` makes the skill *available for the sub-agent to read on demand* — it does not reliably paste the full body into context at startup. Under a `no-fetching, from-memory-only` probe the agent returned `UNKNOWN` on in-skill facts, then answered them correctly the moment it was allowed to read the file. Read `skills:` as "the sub-agent has this skill and will consult it", not "the content is pre-injected". **Two methodology lessons (both bit here before this resolved):** (a) never feed the distinctive answer into the probe prompt — that measures echo, not recall; (b) never constrain an agent probe to `no fetching` — it blocks the real access path and falsely reads as "broken". Probe agents the way they actually operate.
5. **Tool resolution order** between sub-agent `tools:` allowlist and global permissions (allow/deny/ask) — not explicitly described.
6. **Workflow tool vs Agent tool intersections** — Workflow is a wrapper over Agent with additional primitives. When Workflow is excessive, when it is necessary — the recommendation in §2.2.4 is empirical.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7 + Agent tool live schema):**
- `code.claude.com/docs/en/sub-agents` — frontmatter (`maxTurns`, `tools`, `skills`, `model`), `--agents` JSON.
- `code.claude.com/docs/en/features-overview` — Skill vs Subagent comparison; context isolation rationale.
- `code.claude.com/docs/en/agent-teams` — dimension decomposition pattern, inter-agent communication.
- `code.claude.com/docs/en/tools-reference` — tools inheritance default.
- Agent tool live schema (visible in every session) — 8 invocation attributes.
- Workflow tool live schema — concurrency caps `min(16, cpu_cores - 2)`, 1000-agent lifetime, `schema:` parameter, pipeline/parallel/phase primitives.

**Internal:**
- [docs/layers/decision-tree.md](decision-tree.md) — layer selection when a new artifact appears.
