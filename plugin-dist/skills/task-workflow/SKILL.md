---
name: task-workflow
user-invocable: false
description: "Universal cycle for any task that modifies code, configuration, documentation, or infrastructure — feature, bugfix, refactor, migration, ops work. Cycle: triage → recon → plan (file when ≥ 3 phases) → parallel dispatch → synthesis → advisor → execution → verification → out-of-scope tickets → edge-case sweep → advisor → git safety → commit → report. Plan files land in `~/.claude/plans/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md` — outside the project, not tracked by git, persistent across sessions. Adapts to both interactive sessions (uses `EnterPlanMode` / `ExitPlanMode` when present) and unattended auto-runs (writes the plan file directly, no blocking gate). Size and urgency do not bypass the cycle; they only change which conditional steps activate."
when_to_use: "Trigger on any modifying task — explicit «сделай / пофикси / добавь / реализуй / зарефактори / обнови / настрой / разверни / удали», multi-file refactors, bug fixes, feature work, ops changes, doc edits that change instructions. Does not run on read-only questions («что в этом файле / как работает X / где найти Y / объясни архитектуру Z») — those bypass the cycle entirely. «Маленькая правка», «срочно», «один файл» are not exceptions — they only change which conditional steps activate (plan file, sub-agents); advisor and verification stay unconditional."
---

# Task workflow

Universal cycle for any task that modifies code, configuration, documentation, or infrastructure.

## Top-level rule

Size and urgency are not exceptions. «Маленькая правка», «срочно», «один файл» do not skip steps. They only change which *conditional* steps run — plan file is conditional on ≥ 3 phases; sub-agent dispatch is conditional on recon scope; advisor and verification stay unconditional.

«This is too small for X» is the most reliable signal that you are about to drop a step you should not drop.

## Mode awareness

The cycle adapts to two modes:

- **Interactive session** (human at the keyboard, responds within a minute): `EnterPlanMode` / `ExitPlanMode` / `AskUserQuestion` are available and meaningful. The Plan step uses the tool when applicable.
- **Unattended auto-run** (long autonomous prompts, scheduled tasks, headless `claude -p`): `EnterPlanMode` and `AskUserQuestion` block on user consent and may freeze the run for hours. The Plan step writes the audit file directly; no gate.

**Detection — observable signals only**, not self-assessment:

1. If a system reminder declares auto mode (e.g. `## Auto Mode Active`) at session start or during the session → **auto**.
2. If invoked headlessly (`claude -p` without an interactive TTY) → **auto**.
3. Otherwise → **interactive**.

When in doubt — prefer auto (safer default; the user's primary workflow is unattended runs). «Could the user respond in seconds?» is not a reliable signal — the model cannot measure that.

## Cycle

### 1. Triage (one question)

Is the task **ambiguous**? — new feature with unclear requirements, design fork, two reasonable approaches with non-obvious trade-offs.

- Ambiguous → brainstorm first. State the alternatives, identify the constraint that resolves the fork.
  - Interactive: `AskUserQuestion` to surface the fork.
  - Auto: pick the most plausible interpretation, record the assumption in the plan file (or in the report if no plan file), proceed.
- Not ambiguous (explicit bugfix, known pattern, narrow change) → proceed to Recon.

Do not confuse «ambiguous» with «small». A small change with one obvious approach skips brainstorm; an ambiguous one does not, regardless of size.

### 2. Recon-first (always)

Before any tool dispatch or substantive write:

- Read 3-5 files along the dependency chain — model → schema → service → API → frontend; or token → component → page for UI. Not only the file you will edit. Most regressions start from an incomplete picture.
- If the change touches a library / framework / API / language syntax (including regex flavours, JSON / TOML parsers, datetime libraries, build tool flags) — query Context7 first (`resolve-library-id` → `query-docs`). Memory drifts; verify.
- If recon needs more than 5 files or more than 3 search angles — dispatch `Explore` sub-agents in parallel, one per angle, in one message.

Recon trades minutes now against hours of regression debugging later. Skipping is the most expensive optimisation.

### 3. Plan — audit file when ≥ 3 phases or ≥ 3 edge-cases

Write an audit file before dispatching execution work when **either**:
- The task decomposes into 3+ phases with dependencies, OR
- Recon surfaced 3+ edge-cases / risks worth tracking.

Below those thresholds — skip the audit file; the cycle below still runs.

**Two paths exist — they serve different roles, do not conflate.**

| Role | Path | Owner | Lifetime |
|---|---|---|---|
| Tool plan file (interactive `EnterPlanMode` only) | `~/.claude/plans/<random-kebab-slug>.md` (e.g. `typed-forging-glacier.md`) — flat, no hierarchy, no date | Claude Code tool (path injected via plan-mode system message) | Single session, may be reused or replaced by the tool |
| Hub audit copy (always) | `~/.claude/plans/audit/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md` — hierarchical, dated | This skill | Persistent across sessions, audit trail |

Verified empirically against Claude Code plan mode (2026-05-30 inspection): the tool-controlled path is flat with a random slug; ours is a parallel audit convention living under the `audit/` subdirectory so it does not collide.

**Audit path components:**
- `<basename(cwd)>` — `basename "$(pwd)"` — derives the project segment automatically, no per-project configuration.
- `<YYYY-MM-DD>` — today's date in ISO.
- `<topic>` — short kebab-case slug from the task headline (≤ 6 words).

`mkdir -p` the directory; the audit copy lives outside any project, is never tracked by git, and persists across sessions. Audit retrospectively with `ls ~/.claude/plans/audit/<project>/`.

**Format (mirrors Claude Code plan mode Phase 4 instructions, extended with phases / risks / retrospective):**

```markdown
# <Topic title>

> Project: <basename(cwd)>
> Date: <YYYY-MM-DD>
> Type: <feature | fix | refactor | migration | ops | docs>
> Mode: <interactive | auto>

## Context

[Why this change — the problem or need it addresses, what prompted it, the intended outcome. 1-3 sentences.]

## Recommended approach

[The chosen approach (not all alternatives). What will be done at a high level.]

## Critical files

- `path/to/file1` — what changes / what is reused
- `path/to/file2` — what changes / what is reused

## Phases

1. <phase name> — [files] — [depends on previous? yes/no]
2. <phase name> — [files] — …
3. …

## Risks

- <risk>: <mitigation>

## Verification

[How to test end-to-end: run the code, run MCP tools, run tests. Specific commands.]

---

## What actually happened (filled retroactively after execution)

[Deviations from plan, why; surprises; what cost more / less than expected.]
```

**Interactive mode** — follow tool plan mode's 5-phase workflow:
1. Enter plan mode (`EnterPlanMode`); tool injects the plan file path into the system message.
2. **Phase 1: Explore** — dispatch `Explore` agents in parallel (1-3 max) to understand the codebase.
3. **Phase 2: Plan** — dispatch `Plan` agents (1-3) to design the approach from different angles.
4. **Phase 3: Review** — read critical files, surface remaining questions via `AskUserQuestion`.
5. **Phase 4: Write** — write the plan into the tool's plan file (the path given in the system message). Simultaneously write the same content into the hub audit copy at `~/.claude/plans/audit/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md` for persistent audit.
6. **Phase 5: ExitPlanMode** — request approval.

**Auto mode** — Phase 1-4 of the same workflow but without the tool:
1. Skip `EnterPlanMode` (it would block on user consent).
2. Phase 1 Explore + Phase 2 Plan still run (`Explore` and `Plan` agent types are available in both modes).
3. Phase 3 Review — internal reasoning instead of `AskUserQuestion`.
4. Phase 4 Write — only the hub audit copy at `~/.claude/plans/audit/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md`.
5. Proceed to Step 4 of this cycle (no Phase 5).

### 4. Parallel dispatch of investigation sub-agents

Independent investigation tasks dispatch in **one message** with multiple `Agent` calls. Sequential calls in main context waste turns and fill the parent context with raw tool output.

In every sub-agent prompt — required fields:
- **Path restriction:** «Operate inside `<cwd>` only. Do not Read / Glob / Grep outside that root.»
- **Return cap:** «Reply in ≤ N words / lines» (pick N by depth: 200 for quick recon, 600 for deep dive).
- **Format:** exact structure expected — sections, headers, `file:line` citations.
- **Concrete deliverable:** «Return paths with line ranges, not generalities» / «Return the failing assertion, not a description of it».

Prompts to sub-agents are English regardless of conversation language — models follow English more precisely and spend fewer tokens.

### 5. Synthesis in main context

Sub-agent outputs go through synthesis, not dump.

Boil down to ≤ 200 words: convergent findings, divergent findings, gaps. Copying agent replies wholesale defeats the orchestration value — main context fills with raw tool output instead of decisions.

### 6. Decision review → Advisor #1 (before substantive work)

Once a leading approach exists from synthesis, gate it before any writing or large dispatch. Two checks, **in this order** — the deep review first, the advisor last:

**6a. High cost-of-being-wrong → dispatch `decision-reviewer` FIRST.** When the synthesised approach is an architecture choice, hard-to-reverse, broad-blast-radius, or expensive-to-undo decision, dispatch the `decision-reviewer` agent on that approach **before** the advisor call. It is adversarial, grounded, and fed only the artifact — so the prompt must carry the chosen approach, the alternatives weighed, the load-bearing assumptions, and the affected files/paths (it sees **only your prompt**, not this session; a one-line «review this» starves it). Conditional on stakes — a low-stakes change skips 6a and goes straight to 6b. Do **not** fold this into the advisor call; they are different checks (advisor: holistic, sees your framing; decision-reviewer: adversarial, artifact-only).

**6b. Then `advisor()` as the final checkpoint.** Call `advisor()` after synthesis **and after any decision-review** — so the advisor sees the reviewer's verdict in the transcript and makes the last call before substantive work: proceed, or turn back to further investigation / redesign.

- Round cap: 3. If round 3 still surfaces new material — the approach is wrong; stop, escalate to user, do not run a 4th round.
- A critical advisor finding → revise plan / approach, re-call.
- A passed advisor → proceed.

### 7. Approval (interactive) / proceed (auto)

- **Interactive + plan file exists:** wait for `ExitPlanMode` approval. The approval IS the execution authorization — no extra «when to start?» turn. `ExitPlanMode`'s `allowedPrompts` already captures the granted permissions.
- **Interactive + no plan file:** the synthesised plan is presented inline; proceed unless the user objects within the same turn.
- **Auto-mode:** proceed.

A casual «ок / sounds good» in regular chat is not a substitute for `ExitPlanMode` approval on a non-trivial change with a written plan. If a plan file exists in interactive mode, route through the gate.

### 8. Execution

Dispatch specialised sub-agents for the work itself — one per independent piece. In every execution prompt:

- **Path restriction** (same as Recon).
- **TDD where it applies** (business logic, validators, lifecycle, calculations, bug fixes): explicit «write a failing test first, then minimal code, then refactor». See [`testing-strategy`](../testing-strategy/SKILL.md) for the test level decision.
- **Concrete `file:line` targets** — not «find and fix», but «edit `service.ts:120-145`, function `processOrder`, condition on line 132».
- **Anti-regression scope:** «do not change `<list of adjacent files>` even if you spot opportunities» — those are tickets, not edits.
- **Verification command:** «after the edit, run `<lint | typecheck | test>` and report the result».

Independent execution phases dispatch in parallel (one message, multiple `Agent` calls). Dependent phases run sequentially.

Specialised agents — pick by the project's stack. If the project has a `CLAUDE.md` listing specialised agents (e.g. `backend-python-developer`, `enterprise-react-developer`), use those. Otherwise dispatch a `general-purpose` sub-agent with explicit constraints.

### 9. Verification after each execution sub-agent

Do not trust the agent's «done» without verification:

- `grep` the changed file for the assertion the agent claims to have added / removed.
- Run the lint / typecheck / test command the agent was told to run; read the output, not just the exit code.
- Read the first 30 lines of changed files — catches surprise mass-rewrites and accidental file replacement.
- `find . -name ".claude" -type d 2>/dev/null` from the project root — sub-agents occasionally leak transient state directories; clean them.

Mismatch → targeted follow-up to the same agent with the specific gap, not «try again». Re-dispatch on the same target cap: 2.

### 10. Out-of-scope findings → ticket

Any problem the agent (or recon) found that is **not** being fixed in this change → ticket via [`surface-ticket`](../surface-ticket/SKILL.md) before declare-done. This covers adjacent bugs, anti-patterns, postponed refactors, partial implementations left in place. The decision to not fix now IS the trigger.

Fixed inline within scope — no ticket. Trivially safe cosmetic fixes (typo in comment, single rename) may apply inline — say so afterwards.

### 11. Edge-case sweep (after implementation)

One pass over the changed files for missed scenarios — empty / null / boundary inputs, concurrent operations, error paths, partial state, timeouts, retries, idempotence. One round only. Findings → fix inline if in scope, or ticket via [`surface-ticket`](../surface-ticket/SKILL.md).

If a dedicated edge-case auditor sub-agent is available, dispatch it; otherwise sweep inline. Do not loop a second round on the same files — perfectionism amplifies and finds non-issues.

### 12. Advisor #2 (mandatory before declare-done)

Before declaring the task complete — `advisor()` once more on the finished result. One round; this is validation, not re-design.

If the advisor surfaces a new issue at this stage — verify it against the actual change. A finding the advisor missed during #1 but caught at #2 is worth fixing; a conflict between advisor and primary-source evidence is worth one reconcile call.

### 13. Git safety check (before destructive operations)

Before `git checkout <sha>`, `git reset --hard`, `git rebase`, `git push --force`, `git commit --amend` on shared commits, database `DROP`, mass `DELETE`, production migration, `rm -rf` with broad scope — stop and answer three questions:

1. Where am I now? (branch vs detached, working tree state, origin tracking)
2. Where will I be after the command? (new HEAD, dangling commits, recoverable via reflog / backup?)
3. Is the whole sequence safe end-to-end, not just this one command?

If any answer is not clear — do not execute. Surface to the user.

### 14. Commit via `git-conventional-commits-ru`

When the change is ready and verified — invoke [`git-conventional-commits-ru`](../git-conventional-commits-ru/SKILL.md). Russian description, English `type/scope/!`, identifier names in backticks, body as bullet list, mixed changes split into atomic commits.

Never emit AI-attribution trailers (`Co-Authored-By: Claude …`, `Generated with Claude Code` and similar).

### 15. Push policy

- Feature / test / topic branches — may push without explicit per-session approval.
- `main` / `master` / any shared release branch — explicit per-session approval required.
- `--force` on a shared branch — never without explicit user request naming that branch by name.
- `--no-verify` — never.

### 16. Report to user

**Multi-phase task** (executed in stages): after each phase a short intermediate report; the next phase starts without asking unless there is a real fork (design choice, blocker, sensitive operation).

**Single-phase task** or **final report** — same shape:

```
Сделано: 1-3 строки — что изменилось.
Проверено: какие команды / файлы — конкретно.
Что осталось: следующая фаза / smoke / push / зависимости от пользователя.
Риски: что может сломаться и как откатить.
```

Style: plain Russian, identifier names in backticks, no emoji unless asked, no «продолжать?» when the next step is obvious from the plan.

**Fill the plan file's «What actually happened» section** after the task lands. Deviations from plan, surprises, what cost more / less. This is the audit value of the plan file — not the plan itself, but the diff between plan and reality.

## Closing common rationalisations

| Excuse | Reality |
|---|---|
| «Это маленькая правка, advisor не нужен» | Advisor is unconditional. Size only adjusts conditional steps (plan file, sub-agents), not advisor. |
| «Срочно, пропустим verification» | Verification separates «agent said done» from «actually done». Urgency is reason to be careful, not careless. |
| «Очевидно, recon не нужен» | Most regressions start from confidence without recon. 3-5 files is 2 minutes. |
| «Один файл, plan не нужен» | One file ≠ one phase. If the change has internal dependencies (data model → migration → service → tests), still ≥ 3 phases — plan file applies. |
| «Я уже делал такое» | New context, new project state, new dependencies. Recon still runs. |
| «Сам сделаю быстрее, чем sub-agent» | True for narrow targeted edits. False for broad investigation. Default to dispatch for anything multi-file or multi-angle. |
| «Тест напишу потом» | Then the change is not done. TDD trigger fires on business logic and bugfixes — see [`testing-strategy`](../testing-strategy/SKILL.md). |
| «Срочно, plan файл лишний» | Plan file is 2 minutes; the audit trail it leaves saves hours when something breaks. Triggered by phases / edge-cases, not by «срочно». |

## When the cycle does NOT apply

Read-only questions only:
- «What's in this file?»
- «How does X work?»
- «Where is Y?»
- «Explain the architecture of Z.»

Anything that **changes** state — files, config, infra, database, deployment — runs the cycle.

## Stop conditions

| Loop | Max rounds |
|---|---|
| Advisor #1 (on approach) | 3 |
| Advisor #2 (final) | 1 |
| Edge-case sweep | 1 |
| Re-dispatch same agent on same target | 2 |

At the cap — stop, do not «keep improving». A loop hitting the cap is a signal the approach is wrong, not that one more round will close it.

## Cross-refs

- [`surface-ticket`](../surface-ticket/SKILL.md) — out-of-scope and postponed findings (Step 10).
- [`testing-strategy`](../testing-strategy/SKILL.md) — test level decision and Red → Green → Refactor (Step 8 TDD).
- [`code-audit`](../code-audit/SKILL.md) — parallel multi-aspect review (alternative to Step 11 edge-case sweep when the surface is broader).
- [`severity-calibration`](../severity-calibration/SKILL.md) — ranking findings honestly (used in advisor responses and reports).
- [`no-suppression-markers`](../no-suppression-markers/SKILL.md) — `TODO` / `FIXME` / `.skip` / disable-comment ban (active throughout — never the resolution to a found issue).
- [`ops-app-server-safety`](../ops-app-server-safety/SKILL.md) — when the work spawns dev servers or `docker compose` stacks (Step 8 verification of running processes).
- [`git-conventional-commits-ru`](../git-conventional-commits-ru/SKILL.md) — commit step (Step 14).
- [`web-search`](../../agents/web-search.md) — authoritative source verification (Step 2 Recon when Context7 misses or surfaces conflict).
- [`decision-reviewer`](../../agents/decision-reviewer.md) — adversarial grounded review of a high-stakes approach (Step 6a, before the advisor checkpoint; conditional on cost-of-wrong).
