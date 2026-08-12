# Layer: Skills

> Optionally activated instruction sets. In the hub: `adapters/claude-code/plugin/skills/<name>/SKILL.md` (+ supporting files), shipped via the `mainframe` plugin.

> Last updated: 2026-06-14 (plugin-migration actualization). Prior: 2026-05-28 (full frontmatter spec + `disable-model-invocation`, `context: fork`).

The hub's `init` skill is the manual primary-session context: it sets `disable-model-invocation: true`, does not use `context: fork`, and is invoked as `/mainframe:init`.

---

## Where it lives / How to install

- In the hub: `adapters/claude-code/plugin/skills/<name>/SKILL.md` (+ optional supporting files directly beside it or one directory below, such as `<name>/references/*.md`).
- On the machine: delivered via the `mainframe` plugin (`adapters/claude-code/plugin/` symlinked as one plugin), not an individual per-skill symlink.
- Activation: once the plugin is loaded, the skill becomes visible to Claude through the frontmatter "showcase".

---

## 1. Canonical reference (Anthropic Claude Code docs)

### 1.1. Full frontmatter

Source: `code.claude.com/docs/en/skills`, `code.claude.com/docs/en/slash-commands` (frontmatter reference).

```yaml
---
name: <kebab-case>                    # display name; defaults to dir name
description: <what it does>           # recommended; up to 1024 chars
when_to_use: <when to trigger>        # additional trigger phrases; appended to description
argument-hint: <[arg1] [arg2]>        # autocomplete hint
arguments: <space-separated or yaml-list>  # named positional args for $name substitution
disable-model-invocation: false       # true → Claude does NOT auto-load skill + NOT preloaded in sub-agents
user-invocable: true                  # false → hide from /-menu
allowed-tools: <subset of tools list> # tools without permission ask
model: <model or 'inherit'>           # override model for the activation turn
effort: <low|medium|high|xhigh|max>   # override effort level
context: <main|fork>                  # fork → skill runs in forked context (isolation)
agent: <type>                         # with context: fork — which agent to fork (e.g. Explore)
---
```

Combined `description + when_to_use` truncated at **1536 chars** (hub validator enforces this).

### 1.2. Depth and supporting files

- A skill = a `<name>/` folder containing `SKILL.md` inside.
- Optional supporting files can live beside `SKILL.md` or in one descriptive
  subfolder such as `references/`, `examples/`, or `scripts/`.
- **Maximum supporting-file depth = 1** below the skill root. Deeper trees are
  rejected by the hub validator.
- Cross-skill `@import` does not exist. Relationships between skills are expressed by mentioning the skill name in the body; both frontmatter entries are visible at session start.

### 1.2.1. Supporting-file loading — the only signal is an inline link (verified 2026-06-13)

When a skill triggers, only `SKILL.md` is injected (one message, persists for the session). Supporting files are **not** injected — the model must choose to `Read` them on-demand. The **only** pointer is what the author writes inline in `SKILL.md`: a relative link `[file.md](file.md)` plus a one-line *what it holds + when to load it* (docs: *"to ensure Claude knows what each supporting file contains and when to load it, reference these files from SKILL.md"*). There is **no** frontmatter `files:` field, no auto-load, no `@import` in the body, and **no documented fix** for the failure where the model stops at `SKILL.md` and skips the link — Anthropic treats link+description as sufficient. Empirically it is not always: an earlier hub skill's linked template was skipped and a wrong-scheme ticket was produced on 2026-06-13.

Escape hatches for a must-load-every-time file: fold it into `SKILL.md` if small. A bash placeholder `` !`cat ${CLAUDE_SKILL_DIR}/file.md` `` can force-inject eagerly, but it is unverified for plugin skills and costs tokens every load — not used. Practical rule: classify each supporting file **conditional** (link + what/when/why is enough) vs **mandatory-every-run** (do not trust a link). Source caveat: the original CLI guide and research pass both rested on `code.claude.com/docs/en/skills` — two retrieval paths to one underlying source, not independent evidence.

### 1.3. Eval — when the model loads a skill

1. At session start, the model sees the frontmatter of all plugin-loaded skills (`description` + `when_to_use`).
2. On tool use / a topical request, the model evaluates relevance and loads the body if there is a match.
3. `user-invocable: true` → skill appears in the `/`-menu (user can invoke it explicitly).
4. `user-invocable: false` → hidden from the menu, but **Claude still auto-invokes it on triggers**.
5. `disable-model-invocation: true` → Claude does NOT auto-invoke. Current
   Anthropic documentation also says that this prevents `skills:` preload into
   subagents. Activation is therefore only explicit `/<name>` when the skill is
   user-invocable, or an explicitly controlled file read by a dedicated agent.

### 1.4. `context: fork` — skill in an isolated context

A skill with `context: fork` runs in a forked context (as a subagent under the hood):
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

Advantage: the skill is not loaded into the main context on auto-trigger; a separate context is used, and a summary is returned.

### 1.5. Skills vs Subagents — separation of concerns

> "Skills are reusable content (instructions, knowledge, or workflows) that you can load into any context, adding to your main context window, and are best for reference material or invocable workflows."
>
> "Subagents are isolated workers with their own context that run separately from your main conversation. They offer context isolation, use a separate context window... Use a subagent when you need context isolation or when your context window is getting full."

A skill can be made closer to a subagent: `context: fork`. A subagent can be made closer to a skill: `skills:` preload. **The boundary is thin**; the choice is in [decision-tree.md](decision-tree.md).

### 1.6. Skills in subagents — access vs preload (finding 2026-06-01)

Two **orthogonal** axes (source: `code.claude.com/docs/en/sub-agents`). This is not about a "different engine" — the engine is the same; what gates it is `tools`:

- **Access** (can a subagent *invoke* a skill) — via the `Skill` tool:
  - `tools:` is specified and **does not contain `Skill`** → invoking a skill is **not possible**.
  - `tools:` is **omitted** → inherits all tools, including `Skill` → can invoke any project/user/plugin skill.
  - To block entirely: remove `Skill` from `tools` **or** add it to `disallowedTools`.
- **Preload** (`skills:` in frontmatter) — injects the **full content** of listed
  model-invocable skills into context at startup. Current Anthropic docs say a
  skill with `disable-model-invocation: true` is excluded from this preload.

**Consequence:** `skills:` is not a reliable private preload for a skill hidden
with `disable-model-invocation: true`. When such knowledge must remain private to
one agent, give that agent a narrow `Read` capability, point it at the skill
entrypoint, and enforce the allowed skill tree with an agent-scoped `PreToolUse`
hook. `mainframe-researcher` uses this pattern without a `skills:` binding: the
agent body points directly to the hidden skill entrypoint, so the primary agent
does not load or route its internal methodology.

---

## 2. Hub usage & ADRs

### 2.1. Current skills in `adapters/claude-code/plugin/skills/`

17 skills as of 2026-08-12, shipped via the `mainframe` plugin. The directory is the source of truth — this is grouped by role rather than re-enumerated per skill, because the per-skill table is exactly what rotted here (it sat at 5 while the count grew). Roles:

- **Process / workflow:** `init`; private `decision-review` is
  read directly by `mainframe-decision-reviewer` and stays outside primary-session
  discovery.
- **Quality discipline (gates / self-checks):** `no-suppression-markers`, `severity-calibration`, `ticket`, `testing-strategy`, `secrets-handling`.
- **Specialist stack patterns:** `python-backend-patterns`,
  `typescript-backend-patterns`,
  `react-frontend-patterns`, `frontend-design`, `shadcn`. These are deliberately
  model-invocable so the primary agent can use them and subagents can preload or
  invoke them. Backend agents preload their compact core. The React agent also
  preloads compact `frontend-design` and `shadcn` entrypoints: they route to
  supporting files only for the active surface, while the shadcn branch exits
  after a local check when `components.json` is absent.
- **Private research methodology:** `research-method`, read only by
  `mainframe-researcher` through its profile-scoped path guard.
- **Ops / external services:** `infrastructure` is the model-visible primary-session entry; `dokploy-api` is its hidden Dokploy branch; `ops-app-server-safety`, `curl-requests`, and `secrets-handling` remain focused reusable capabilities. The infrastructure entry reads a project's adapter-neutral `.agents/infrastructure.json` only when applicable and follows only the referenced runbooks needed for the active operation.

The `description + when_to_use` split in neutral, situation-based phrasing (describe the trigger, not its source) is the standard; combined chars stay within the validator limit (1536).

### 2.2. Hub validator limits

[`tools/validate-skill.py`](../../tools/validate-skill.py) — runtime validator. Triggered on `SessionStart` + `PostToolUse(Edit|Write|MultiEdit)`. Uses local `.venv` (tiktoken + pyyaml). Checks:

| What | Limit |
|---|---|
| SKILL.md body (excluding frontmatter) | 5K tokens / 500 lines |
| Supporting file | 5K tokens / 60 lines |
| `description` | ≤ 1024 chars |
| `description + when_to_use` | ≤ 1536 chars |
| Supporting-file depth | at most one directory below the skill root |
| Dead supporting files | flagged |
| Required frontmatter | `name`, `description` (minimum) |

### 2.3. Hub principles for skills

- **Trigger phrases go in `when_to_use`, not in `description`.** Description = what it does; when_to_use = when to activate. After the 2026-05-28 split, our skills follow this exactly.
- **Neutral, situation-based phrasing — not tied to which side triggers it** (2026-05-28). Describe the trigger, not its source. Formulations like `"Use when the user asks..."` or `"Trigger when Claude is planning..."` are forbidden. Correct: `"Use when starting, restarting, or stopping a long-running development server or container stack."` Rationale — the activation mechanism matches *task* against *description* without distinguishing the source of the task (user message vs. the model's own plan). Style applicability conditions: (a) specificity — vague formulations cause false positives; (b) preserving anchor keywords (commands like `npm run dev`, process names, action verbs).
- **`user-invocable: false` by default**, except for skills with side effects (commit, deploy, scaffold). The criterion is side effects, not invocation frequency.
- **`disable-model-invocation: true`** — use when a skill must not auto-load.
  Do not assume it will still preload through a subagent `skills:` binding;
  current Anthropic documentation explicitly says it will not.
- **Relationships between skills** — expressed by mentioning the skill name in
  the body or preloading it in the owning profile (`severity-calibration` is
  preloaded by `mainframe-decision-reviewer`).

---

## 3. Gray zones / open questions

1. **Skill activation conditions are resolved by the model contextually.** Known (verified 2026-05-28 against `features-overview`): descriptions are visible to Claude on every request in the session, matching is done against "task" (not only the user message — also the model's own plan), specificity beats vagueness, vague descriptions → false positives. The exact matching algorithm is not documented.
2. **Conflicts between skills** with overlapping `when_to_use` — which one gets loaded first? Not documented.
3. **Token budget after compaction** — does the frontmatter stay in the system or get reloaded? Not verified.
4. **Runtime conflict (2026-08-09).** Older hub probes observed
   `disable-model-invocation: true` skills through a subagent `skills:` binding,
   but current Anthropic documentation says this combination does not preload.
   CLI 2.1.226 accepted the binding, but the live semantic probe could not reach
   its first model turn because the organization returned
   `oauth_org_not_allowed`. See §1.6; do not depend on the disputed behavior.

---

## Sources

**Authoritative (Anthropic Claude Code docs via Context7):**
- `code.claude.com/docs/en/skills` — format, frontmatter, eval, `context: fork`.
- `code.claude.com/docs/en/slash-commands` — frontmatter reference (full field list).
- `code.claude.com/docs/en/plugins` — SKILL.md in plugins.
- `code.claude.com/docs/en/features-overview` — Skill vs Subagent comparison.
- `code.claude.com/docs/en/sub-agents` — `skills:` preload in sub-agents.

**Related:**
- `tools/validate-skill.py` — runtime validator.
- [decision-tree.md](decision-tree.md) — layer selection when a new artifact appears.
