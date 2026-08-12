# Layer: Agents (sub-agents)

> Isolated subagents with their own context. In the hub: `adapters/claude-code/agents/<name>.md` (6 agents), delivered at user scope under `~/.claude/agents/mainframe/`.

> Last updated: 2026-08-11 (infrastructure moved from a subagent to a primary-session skill). Prior: 2026-08-09 (user-level agent delivery).

---

## Where it lives

- In the hub: `adapters/claude-code/agents/<name>.md` — one markdown file per agent.
- On the machine: the whole source directory is symlinked to `~/.claude/agents/mainframe/`. Claude Code scans user-agent directories recursively; the subdirectory is organization only and does not change identity.
- Activation: each profile has a collision-safe `mainframe-<name>` identifier and is invoked through `Agent(subagent_type: "mainframe-<name>")`.

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

Body — system prompt of the file-based subagent. `prompt` belongs to the JSON
form accepted by `--agents`; it is not documented as file frontmatter.
```

### 1.2.1. Full frontmatter (documented — `code.claude.com/docs/en/sub-agents`)

Previously it was assumed that the semantics of additional fields (`hooks`, `mcpServers`, `memory`) were "not described explicitly" — this was a gray zone. The list is now complete and documented:

| Field | Purpose | Note |
|---|---|---|
| `name` | agent id (required) | Hooks receive this value as `agent_type` |
| `description` | when to delegate (required) | visible to the main Claude |
| `tools` | allowlist | **Omitted → inherits ALL tools, including `Skill`.** Specified → only those listed |
| `disallowedTools` | block-list | remove a tool from inherited/specified |
| `model` | `sonnet`/`opus`/`haiku`/`fable`/full-id/`inherit` | default `inherit` |
| `maxTurns` | ceiling on agentic turns | soft enforcement (see §3.1) |
| `skills` | preload | injects the **full content** of the skill into context at startup; the "what is preloaded" axis, NOT "what is accessible" (access is via `tools`/`Skill`) |
| `permissionMode` | permission mode | Supported for user agents; parent `auto`, `acceptEdits`, or `bypassPermissions` can take precedence |
| `mcpServers` | MCP servers for the agent | Supported for user agents; inline servers connect only for that agent |
| `hooks` | lifecycle hooks in the agent scope (all events; `Stop` → `SubagentStop`) | Supported for user agents |
| `memory` | `user`/`project`/`local` | cross-session memory |
| `background` | boolean | `true` always uses background execution |
| `effort` | `low`/`medium`/`high`/`xhigh`/`max` | overrides session effort when supported by the selected model |
| `isolation` | `worktree` | runs the agent in a temporary worktree |
| `color` | named UI color | task-list and transcript presentation |
| `initialPrompt` | initial user turn | used only when the agent runs as the main session through `--agent` or the `agent` setting |

> **Hub delivery decision (2026-08-09):** Claude Code intentionally ignores `permissionMode`, `mcpServers`, and `hooks` on plugin-shipped agents. MAINFRAME therefore keeps shared skills and global hooks in the plugin but delivers profiles from `adapters/claude-code/agents/` at user scope. Agent `skills:` entries use canonical plugin identifiers such as `mainframe:decision-review`. Cross-agent hooks still belong in the plugin's global `hooks.json`; profile-only hooks and MCP servers may now live in the owning agent.

### 1.3. Agent tool — invocation schema

Attributes live in the schema of the Agent tool itself (visible to the main Claude in every session):

| Attribute | Purpose |
|---|---|
| `description` | Short (3-5 words) task description — appears in UI and telemetry |
| `prompt` | Full prompt to the subagent. In English (see §2.2.1) |
| `subagent_type` | Name of a custom agent (from `adapters/claude-code/agents/`) or built-in (Explore / Plan / general-purpose / claude-code-guide / statusline-setup) |
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
- The **full** CLAUDE.md memory hierarchy the main session loads — managed-policy + **user-global `~/.claude/CLAUDE.md`** + project `./CLAUDE.md` + `CLAUDE.local.md`. Named custom/plugin subagents are NOT scoped to project-only; the user-global file (the hub's `adapters/claude-code/export/CLAUDE.md`) IS loaded into them. Explore and Plan are the only two that skip CLAUDE.md (and git status), with no frontmatter knob to change that. So an agent body may rely on the umbrella CLAUDE.md being present — but the markdown link to it is human navigation only; the content arrives as loaded memory, not via the link. Source: the `sub-agents` doc ("Explore and Plan are the only subagents that omit CLAUDE.md and git status") + the `memory` doc, corroborated by claude-code-guide (which reports an in-CLI check — relayed, not witnessed here). Checked 2026-06-15.
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
- **Nesting**: since CLI **2.1.172** (2026-06-10) a subagent **can** spawn subagents, up to **5 levels** deep in the locally verified generation (per the then-current changelog; the exact depth was relayed, not runtime-probed). Before 2.1.172, nesting was blocked — `Agent` / `Task` silently filtered inside a subagent (issue #61993). Gating: an agent whose `tools:` omits `Agent` still cannot spawn, by design (inferred from the same allowlist mechanism verified for `Skill` this session) — e.g. the hub's narrow-tools `*-engineer` agents. This depth is version-sensitive and must be rechecked before relying on it.

---

## 2. Hub usage

### 2.1. Current agents in `adapters/claude-code/agents/`

6 agents, delivered at user scope; their supporting skills remain in the `mainframe` plugin. Infrastructure work remains in the primary session through the model-invocable `infrastructure` skill because environment choice, credentials, downtime, and authority commonly require its full task and user context.

| Agent | Purpose | Activation |
|---|---|---|
| `mainframe-decision-reviewer` | Independent, evidence-grounded review of a proposed decision / design / approach before it is locked in (architecture, high cost-of-wrong). Read-only. Its private `decision-review` method is hidden from the primary session and read explicitly from the installed skill path; it is not listed in `skills:` because Claude Code excludes hidden skills from preload. | `Agent(subagent_type: "mainframe-decision-reviewer")`; required by `init/workflow.md` for complex-task preparation |
| `mainframe-python-backend-engineer` | Server-side Python across FastAPI, Django, Flask, and established services, including authentication, workers, realtime, object storage, and external integrations. Its compact `python-backend-patterns` entrypoint preserves the active stack and loads only the matching framework or concern references. Write-capable. | auto-dispatch on a Python backend task |
| `mainframe-typescript-backend-engineer` | Server-side TypeScript across NestJS / Express / Fastify and the Next.js server layer via the version-aware `typescript-backend-patterns` skill. Preserves established stacks and uses the target layer for new or isolated work. Write-capable. | auto-dispatch |
| `mainframe-react-frontend-engineer` | Client-facing React across Vite and the Next.js client layer. It preloads compact `react-frontend-patterns`, `frontend-design`, and `shadcn` routers; detailed guidance loads only for the active user-facing surface and an actually detected shadcn project. Write-capable. | auto-dispatch |
| `mainframe-test-auditor` (model: sonnet, effort: medium) | Explicit audit of existing regression evidence, reliability, and execution cost. It runs existing tests, preloads `testing-strategy` and `ticket`, and can verify external contracts through Context7 and primary web sources. It may create or update confirmed open tickets. An agent-scoped hook rejects `Write` and `Edit` outside `docs/tickets/open/`; it never implements fixes or writes tests. | Explicit audit request or `Agent(subagent_type: "mainframe-test-auditor")`; not a routine post-implementation gate |
| `mainframe-researcher` (model: sonnet, effort: medium) | External research from caller-supplied context through Context7 and current authoritative sources. It selects every applicable private domain profile; hooks reject external research until profile preparation begins and restrict `Read` to that tree plus its own persisted fetch results. It does not inspect the repository or make the caller's decision. | Automatic delegation for broad research, or `Agent(subagent_type: "mainframe-researcher")` |

Methodology for selecting model + effort for new agents — internal skill `agent-tournament` (project-scoped in MAINFRAME).

### 2.2. Subagent discipline (research 2026-05-29)

Subagent launch discipline was developed through research. Basic rules are in [adapters/claude-code/export/CLAUDE.md](../../adapters/claude-code/export/CLAUDE.md) Orchestration; details here.

#### 2.2.1. English prompts

All subagent prompts are in English, regardless of the language of the conversation with the user. Hub principle #3 + Anthropic prompt-engineering guidance (models are tuned on English, follow instructions more precisely, fewer tokens for the same content). Applies to the `prompt:` parameter of the Agent tool, the body of `adapters/claude-code/agents/<name>.md`, and prompts inside Workflow. User-facing replies remain in the user's language.

#### 2.2.2. Anti-runaway

Surface — Claude Code CLI: main session + Agent tool invocation of file-based subagents from `~/.claude/agents/`. Verified hard knobs:

| Knob | Where | Effect | Source |
|---|---|---|---|
| `tools: [...]` allowlist | frontmatter | Structurally blocks entire categories. Without `WebSearch` in the allowlist — the subagent physically cannot search. | sub-agents page |
| `maxTurns: N` | frontmatter | "Maximum number of agentic turns before the subagent stops" | sub-agents #supported-frontmatter-fields + tools-reference #agent-tool-behavior |
| `disallowedTools: [...]` | frontmatter | Block-list — remove a specific tool from inherited without full enumeration. | sub-agents |
| `permissionMode` | frontmatter | Supported for these user agents. Parent `bypassPermissions` or `acceptEdits` takes precedence; parent `auto` makes the agent inherit auto and ignores this field. | sub-agents #permission-modes |
| `permissionMode: dontAsk` | frontmatter | Auto-deny prompts when the parent mode permits an agent override. | sub-agents |
| `background: true` | frontmatter | Always use the background path, preserving the primary-session interaction. Before 2.1.186 permission prompts were auto-denied; current versions surface them in the main session with the requesting agent named. | sub-agents |
| `PreToolUse` hook with exit code 2 | external layer | Block specific commands inside an allowed tool (e.g. allow Bash but reject SQL writes). | sub-agents #conditional-rules-with-hooks |

Tool availability differs between foreground and background agents and changes across Claude Code versions. Treat the current official `sub-agents#available-tools` table and the installed runtime as authoritative. Keep `tools:` as the primary structural boundary; `permissionMode` is conditional on the parent session mode.

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

Convention for every `adapters/claude-code/agents/<name>.md`:

- **Routing-only `description`.** Anthropic documents no size limit for this
  field. MAINFRAME targets 250-600 characters and rejects more than 800 as its
  own authoring discipline. Name the matching task, useful stack or artifact
  signals, and only the nearest collision boundaries. Workflow, recon, tools,
  model, skills, background behavior, and report format belong elsewhere.
- **No agent `when_to_use`.** File agents do not support that field. Keep one
  high-signal native description; do not fill the available space or duplicate
  every agent in `init` without measured routing evidence.
- **Narrow `tools:` allowlist** — the agent does only what it was created for. Structural cap > prompt cap.
- **The `tools:` allowlist is the mandatory hard knob.** Default convention for every `adapters/claude-code/agents/<name>.md`: list only the tools the role needs. `permissionMode` is defense in depth because the parent session can override it. `maxTurns` is NOT a default — it is a runaway backstop for genuinely open-ended workers, set generously above the expected turn count; **omit it on write-capable multi-step agents** (a low cap terminates them mid-task — see §3.1). Precedent: the engineer agents had `maxTurns` removed after it killed them mid-task.
- **Soft patterns — supplement, not replacement.** Include the triad (ordinal cap + label + unconditional return) in the prompt as a fallback and for task specifics, not as primary enforcement.
- **`model:` per task type** — sonnet/haiku by default; opus only if the task genuinely requires its capabilities.
- **Specialist skills** are better than pulling domain knowledge into the main
  CLAUDE.md. Keep a reusable capability model-invocable when the primary agent
  may also need it; preload only the role's compact core and let an agent with
  the `Skill` tool invoke conditional capabilities when their concern appears.
  Reserve a disabled skill plus an explicit guarded path for knowledge that is
  intentionally private to one role.
- **`disable-model-invocation: true`** for private domain skills keeps them out
  of the main context, but also excludes them from documented subagent preload.
- **English body** (principle #3).
- **Project-agnostic** (principle #1) — the agent does not know project names or frameworks as mandatory.
- **Neutral dispatch by default.** `Use proactively` is reserved for a deliberate
  product decision to encourage automatic delegation; it is not filler or a
  general quality signal.

---

## 3. Gray zones / open questions

1. **`maxTurns:` enforcement — soft.** Empirically verified across 108 invocations in tournament: `maxTurns: 10` is violated by some variants (max observed 16 turns — haiku-low, up to 1.6× cap). Among sonnet+haiku × low/medium/high — only sonnet-medium gave 0/18 violations, the rest 1-2/18. Documented as a "hard knob" in Anthropic spec, but runtime is partial enforcement. Do not rely on it as a structural guarantee; treat as a soft target. Tool inheritance, deny patterns, `permissionMode` remain the primary protection. **Soft means imprecise, not absent:** the cap still fires, just later than N — so a low cap still cuts a long task off mid-work (the starvation failure mode), while a generous cap rarely binds. NB surface: the agent-SDK `agent-loop` docs describe a cleaner `max_turns` (counts tool-use turns; `error_max_turns` + session resume on hit) — that is the **SDK** surface, not the **CLI** file-based-agent surface this hub targets; the soft-enforcement finding above is the CLI reality.
2. ✓ **RESOLVED (2026-08-09).** Full frontmatter schema is documented — see §1.2.1. Because plugin agents ignore `permissionMode`, `mcpServers`, and `hooks`, MAINFRAME agents moved to user scope. `disallowedTools` is canonical camelCase.
3. **SUPERSEDED (2026-08-09).** `skills:` preloads model-invocable skills, but
   current Anthropic documentation excludes skills carrying
   `disable-model-invocation: true`. See [skills.md §1.6](skills.md).
4. **SUPERSEDED (2026-08-09).** The earlier Dokploy probe proved that an agent
   could locate and read its skill, not that the disabled body was injected at
   startup. A raw Desktop 2.1.222 transcript showed `mainframe-researcher`
   explicitly reading its disabled `SKILL.md` as its first tool call. Private
   knowledge now uses an explicit link and a guarded `Read` path rather than the
   disputed binding.
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
