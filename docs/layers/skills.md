# Layer: Skills

> Optionally activated instruction sets. In the hub: `adapters/claude-code/plugin/skills/<name>/SKILL.md` (+ supporting files), shipped via the `mainframe` plugin.

> Last updated: 2026-06-14 (plugin-migration actualization). Prior: 2026-05-28 (full frontmatter spec + `disable-model-invocation`, `context: fork`).

The hub's `init` skill is the manual primary-session context: it sets `disable-model-invocation: true`, does not use `context: fork`, and is invoked as `/mainframe:init`.

---

## Where it lives / How to install

- In the hub: `adapters/claude-code/plugin/skills/<name>/SKILL.md` (+ optional `<name>/*.md` supporting files). Depth is strictly = 1.
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
- Optional supporting markdown files in the same folder (`<name>/helper.md` etc.).
- **Depth = 1**: nested subfolders are not supported.
- Cross-skill `@import` does not exist. Relationships between skills are expressed by mentioning the skill name in the body; both frontmatter entries are visible at session start.

### 1.2.1. Supporting-file loading — the only signal is an inline link (verified 2026-06-13)

When a skill triggers, only `SKILL.md` is injected (one message, persists for the session). Supporting files are **not** injected — the model must choose to `Read` them on-demand. The **only** pointer is what the author writes inline in `SKILL.md`: a relative link `[file.md](file.md)` plus a one-line *what it holds + when to load it* (docs: *"to ensure Claude knows what each supporting file contains and when to load it, reference these files from SKILL.md"*). There is **no** frontmatter `files:` field, no auto-load, no `@import` in the body, and **no documented fix** for the failure where the model stops at `SKILL.md` and skips the link — Anthropic treats link+description as sufficient. Empirically it is not always (a hub agent skipped `surface-ticket/template.md` and produced a wrong-scheme ticket, 2026-06-13).

Escape hatches for a must-load-every-time file: fold it into `SKILL.md` if small, or name it imperatively from an external hook (POSTURE does this for `task-workflow/flow.md`). A bash placeholder `` !`cat ${CLAUDE_SKILL_DIR}/file.md` `` can force-inject eagerly, but it is unverified for plugin skills and costs tokens every load — not used. Practical rule: classify each supporting file **conditional** (link + what/when/why is enough) vs **mandatory-every-run** (do not trust a link). Source caveat: `claude-code-guide` (CLI) + `web-search` both rest on `code.claude.com/docs/en/skills` — corroborated by two paths, not an independent binary inspection.

### 1.3. Eval — when the model loads a skill

1. At session start, the model sees the frontmatter of all plugin-loaded skills (`description` + `when_to_use`).
2. On tool use / a topical request, the model evaluates relevance and loads the body if there is a match.
3. `user-invocable: true` → skill appears in the `/`-menu (user can invoke it explicitly).
4. `user-invocable: false` → hidden from the menu, but **Claude still auto-invokes it on triggers**.
5. `disable-model-invocation: true` → Claude does NOT auto-invoke. Activation only via explicit `/<name>` (if user-invocable) or subagent `skills:` preload.

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
- **Preload** (`skills:` in frontmatter) — injects the **full content** of the listed skills into context at startup, bypassing semantic matching. Verbatim: *"controls which skills are preloaded, not which skills the subagent can access"*.

**Consequence:** a subagent without `Skill` in `tools` and without the required skill in `skills:` **cannot reach** that skill by any means — neither by auto-match nor by explicit invocation. Therefore a reminder hook must carry knowledge **inline**, not as "go read the skill" (the subagent may physically be unable to). All our hub agents have a narrow `tools:` without `Skill`; they access skills only via `skills:` preload.

---

## 2. Hub usage & ADRs

### 2.1. Current skills in `adapters/claude-code/plugin/skills/`

18 skills as of 2026-06-14, shipped via the `mainframe` plugin. The directory is the source of truth — this is grouped by role rather than re-enumerated per skill, because the per-skill table is exactly what rotted here (it sat at 5 while the count grew to 18). Roles:

- **Process / workflow:** `task-workflow`, `code-audit`, `decision-review`, `git-conventional-commits`.
- **Quality discipline (gates / self-checks):** `no-suppression-markers`, `severity-calibration`, `surface-ticket`, `testing-strategy`, `secrets-handling`.
- **Stack patterns (preloaded into the engineer agents via `disable-model-invocation: true`):** `python-backend-patterns`, `nestjs-backend-patterns`, `nextjs-backend-patterns`, `react-frontend-patterns`, `frontend-design`, `shadcn`.
- **Ops / external services:** `ops-app-server-safety`, `dokploy-api`, `curl-requests`.

The `description + when_to_use` split in neutral, situation-based phrasing (describe the trigger, not its source) is the standard; combined chars stay within the validator limit (1536).

### 2.2. Hub validator limits

[`tools/validate-skill.py`](../../tools/validate-skill.py) — runtime validator. Triggered on `SessionStart` + `PostToolUse(Edit|Write|MultiEdit)`. Uses local `.venv` (tiktoken + pyyaml). Checks:

| What | Limit |
|---|---|
| SKILL.md body (excluding frontmatter) | 5K tokens / 500 lines |
| Supporting file | 5K tokens / 60 lines |
| `description` | ≤ 1024 chars |
| `description + when_to_use` | ≤ 1536 chars |
| Depth | exactly 1 |
| Dead supporting files | flagged |
| Required frontmatter | `name`, `description` (minimum) |

### 2.3. Hub principles for skills

- **Trigger phrases go in `when_to_use`, not in `description`.** Description = what it does; when_to_use = when to activate. After the 2026-05-28 split, our skills follow this exactly.
- **Neutral, situation-based phrasing — not tied to which side triggers it** (2026-05-28). Describe the trigger, not its source. Formulations like `"Use when the user asks..."` or `"Trigger when Claude is planning..."` are forbidden. Correct: `"Use when starting, restarting, or stopping a long-running development server or container stack."` Rationale — the activation mechanism matches *task* against *description* without distinguishing the source of the task (user message vs. the model's own plan). Style applicability conditions: (a) specificity — vague formulations cause false positives; (b) preserving anchor keywords (commands like `npm run dev`, process names, action verbs).
- **`user-invocable: false` by default**, except for skills with side effects (commit, deploy, scaffold). The criterion is side effects, not invocation frequency.
- **`disable-model-invocation: true`** — use when a skill **must not auto-load in main context**, but only be preloaded in a dedicated subagent. Used by the stack-pattern skills (e.g. `python-backend-patterns`), each preloaded into its engineer agent via `skills:` and hidden from the main context.
- **Relationships between skills** — expressed by mentioning the skill name in the body (`severity-calibration` is referenced in `code-audit`).

---

## 3. Gray zones / open questions

1. **Skill activation conditions are resolved by the model contextually.** Known (verified 2026-05-28 against `features-overview`): descriptions are visible to Claude on every request in the session, matching is done against "task" (not only the user message — also the model's own plan), specificity beats vagueness, vague descriptions → false positives. The exact matching algorithm is not documented.
2. **Conflicts between skills** with overlapping `when_to_use` — which one gets loaded first? Not documented.
3. **Token budget after compaction** — does the frontmatter stay in the system or get reloaded? Not verified.
4. ✓ **RESOLVED (2026-06-01).** Sub-agent `skills:` preload verified empirically (hub agents `decision-reviewer` / `*-engineer` start with preloaded skills and work correctly). The access vs preload mechanics have been clarified — see §1.6.

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
