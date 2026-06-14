---
name: task-workflow
user-invocable: false
description: "Universal cycle for any task that modifies code, configuration, documentation, or infrastructure — feature, bugfix, refactor, migration, ops work. Cycle: triage → recon → plan (file when ≥ 3 phases) → parallel dispatch → synthesis → advisor → execution → verification → out-of-scope tickets → edge-case sweep → advisor → git safety → commit → report. Plan files land in `~/.claude/plans/<basename(cwd)>/<YYYY-MM-DD>-<topic>.md` — outside the project, not tracked by git, persistent across sessions. Adapts to both interactive sessions (uses `EnterPlanMode` / `ExitPlanMode` when present) and unattended auto-runs (writes the plan file directly, no blocking gate). Size and urgency do not bypass the cycle; they only change which conditional steps activate."
when_to_use: "Trigger on any modifying task — an instruction to create, fix, add, implement, refactor, update, configure, deploy, or delete, in any language the user writes in; also multi-file refactors, bug fixes, feature work, ops changes, doc edits that change instructions. Does not run on read-only questions (what's in this file / how does X work / where is Y / explain the architecture of Z) — those bypass the cycle entirely. 'It's a small change', 'it's urgent', 'just one file' are not exceptions — they only change which conditional steps activate (plan file, sub-agents); verification stays unconditional and advisor scales to stakes (advisor #1 skipped only on a recon-confirmed trivial low-blast-radius change; advisor #2 stays bar a guarded pure-mechanical edit)."
---

# Task workflow

Universal cycle for any task that modifies code, configuration, documentation, or infrastructure.

## Top-level rule

Size and urgency are not exceptions. "It's a small change", "it's urgent", "just one file" do not skip steps. They only change which *conditional* steps run — plan file is conditional on ≥ 3 phases; sub-agent dispatch is conditional on recon scope; verification stays unconditional. Advisor scales to stakes the same way `decision-reviewer` does (6a): advisor #1 (before-writing) is skipped only on a **recon-confirmed** trivial change — low blast radius (not shared / contract / auth / security, no dependents to break), reversible, obvious approach — decided *after* recon (so blast radius is known, not guessed) and **recorded** in the plan / report; advisor #2 (before-done) stays unconditional bar one guarded pure-mechanical exception (Step 12). Size alone never triggers the skip — only recon-confirmed low blast radius does.

"This is too small for X" is the most reliable signal that you are about to drop a step you should not drop.

## Two phases

The cycle runs in two phases, and the **phase** — not the UI mode flag — decides whether to ask the user.

1. **Discussion / planning** — the user is in the loop (before a `/goal`, an `ExitPlanMode` approval, or an explicit "go"). Widen coverage with recon (dispatch sub-agents), surface forks, and ask **decision-level** questions through `AskUserQuestion`. There is **no cap on the number of questions** — drive by coverage, not a count (5 for a narrow task, 15-20 over hours for a deep one are both right). The phase stays open while a decision-level unknown remains — a fork that changes the outcome and only the user can resolve — and closes when only engineering details are left; those resolve during execution or become tickets. Recon sub-agents exist to surface the decision-level unknowns before execution starts.
2. **Execution** — after the boundary. Work to the goal autonomously, no questions. An out-of-scope or postponable finding → `surface-ticket` and continue. Stop and surface only an un-discussed business-logic / functionality / user-facing change that needs the user's decision — test: "if I choose wrong here, did I commit the product to something the user did not sign off on?" Engineering decisions inside the agreed scope — proceed; never stop for those.

**Boundary** = `/goal` set, plan approved via `ExitPlanMode`, or an explicit "go / run it". Discussion can happen even with the auto-mode UI selected — what matters is whether the user is present to answer, not the mode flag.

**Can the user answer? — gate on phase and presence, not the UI mode flag.**

- **Ask** while you are responding to the user in an active exchange and no boundary has launched execution yet — *even when the auto-mode UI is selected*. Discussion in auto mode is normal; the auto-mode reminder alone does not mean "unattended", and `AskUserQuestion` / `EnterPlanMode` are appropriate here.
- **Do not ask** once execution has launched (post-boundary, running autonomously), or the run is genuinely unattended — headless `claude -p`, a scheduled run, or many turns deep with no human turn. Then pick the most plausible interpretation, record the assumption (plan file, or the report if none), and proceed; reserve a hard stop for an un-discussed business-logic change.

When in doubt during execution — do not block. A frozen unattended run (the user's primary workflow) costs far more than a recorded assumption.

## Cycle

Read [flow.md](flow.md) when a step sends you backward — an advisor turn-back, a re-dispatch, the edge-case loop, a stop-condition cap — and you need to know where the cycle resumes. It is the full control-flow map of every turn-back; the numbered steps below are the forward path.

### 1. Triage (one question)

Is the task **ambiguous**? — new feature with unclear requirements, design fork, two reasonable approaches with non-obvious trade-offs.

- Ambiguous → brainstorm first. State the alternatives, identify the constraint that resolves the fork.
  - User present: surface the fork through `AskUserQuestion`, not a free-text chat question. Phrase the question and every option in plain, concrete language a non-technical reader answers at a glance; lean on the built-in Other for the free-form path. It is non-blocking — the user can pick Other or just type in chat — so prefer it whenever a real decision-fork needs the user, and skip it when there is no fork.
  - Unattended: pick the most plausible interpretation, record the assumption in the plan file (or in the report if no plan file), proceed.
- Not ambiguous (explicit bugfix, known pattern, narrow change) → proceed to Recon.

Do not confuse "ambiguous" with "small". A small change with one obvious approach skips brainstorm; an ambiguous one does not, regardless of size.

### 2. Recon-first (always)

Before any tool dispatch or substantive write:

- Read 3-5 files along the dependency chain — model → schema → service → API → frontend; or token → component → page for UI. Not only the file you will edit. Most regressions start from an incomplete picture.
- If the change touches a library / framework / API / language syntax (including regex flavours, JSON / TOML parsers, datetime libraries, build tool flags) — query Context7 first (`resolve-library-id` → `query-docs`). Memory drifts; verify.
- If recon needs more than 5 files or more than 3 search angles — dispatch `Explore` sub-agents in parallel, one per angle, in one message.

Recon trades minutes now against hours of regression debugging later. Skipping is the most expensive optimisation.

### 3. Plan — audit file when ≥ 3 phases or ≥ 3 edge-cases

Write an audit file before dispatching execution work when **either** the task decomposes into 3+ dependent phases, OR recon surfaced 3+ edge-cases / risks worth tracking. Below those thresholds — skip it; the cycle still runs.

When this step fires, read [plan-file.md](plan-file.md) for the format, the two plan-file paths (interactive tool file vs the always-written hub audit copy), and the interactive-vs-auto workflow. The audit copy persists outside the project (never tracked by git); its value is the diff between plan and reality, filled in at Step 16.

At the same threshold, also seed a `TodoWrite` checklist with the cycle's drop-prone checkpoints — recon, advisor #1, TDD, verify, edge-case sweep, advisor #2, out-of-scope tickets, commit — and mark each as it lands. In a long run the persistent, self-maintained list is the guard against silently dropping a mandatory step; it tracks what you have done, where the skill body only states what to do.

### 4. Parallel dispatch of investigation sub-agents

Independent investigation tasks dispatch in **one message** with multiple `Agent` calls. Sequential calls in main context waste turns and fill the parent context with raw tool output.

Default to `run_in_background: true` when fanning out (several agents, or any long-running one): interleaved foreground replies in the chat are hard to trace afterwards; read each result on its completion notification. Keep foreground only for a single quick agent whose result gates the very next step.

In every sub-agent prompt — required fields:
- **Path restriction:** "Operate inside `<cwd>` only. Do not Read / Glob / Grep outside that root."
- **Return cap:** "Reply in ≤ N words / lines" (pick N by depth: 200 for quick recon, 600 for deep dive).
- **Format:** exact structure expected — sections, headers, `file:line` citations.
- **Concrete deliverable:** "Return paths with line ranges, not generalities" / "Return the failing assertion, not a description of it".

Prompts to sub-agents are English regardless of conversation language — models follow English more precisely and spend fewer tokens.

### 5. Synthesis in main context

Sub-agent outputs go through synthesis, not dump.

Boil down to ≤ 200 words: convergent findings, divergent findings, gaps. Copying agent replies wholesale defeats the orchestration value — main context fills with raw tool output instead of decisions.

### 6. Decision review → Advisor #1 (before substantive work)

Once a leading approach exists from synthesis, gate it before any writing or large dispatch. Two checks, **in this order** — the deep review first, the advisor last:

**6a. High cost-of-being-wrong → dispatch `decision-reviewer` FIRST.** When the synthesised approach is an architecture choice, hard-to-reverse, broad-blast-radius, or expensive-to-undo decision, dispatch the `decision-reviewer` agent on that approach **before** the advisor call. It is adversarial, grounded, and fed only the artifact — so the prompt must carry the chosen approach, the alternatives weighed, the load-bearing assumptions, and the affected files/paths (it sees **only your prompt**, not this session; a one-line "review this" starves it). Conditional on stakes — a low-stakes change skips 6a and goes straight to 6b. Do **not** fold this into the advisor call; they are different checks (advisor: holistic, sees your framing; decision-reviewer: adversarial, artifact-only).

**6b. Then `advisor()` as the final checkpoint — conditional on stakes, mirroring 6a.** Call `advisor()` after synthesis **and after any decision-review** — so the advisor sees the reviewer's verdict in the transcript and makes the last call before substantive work: proceed, or turn back to further investigation / redesign. **Skip this before-writing call only on a recon-confirmed trivial change** — low blast radius (not shared / contract / auth / security, no dependents to break), reversible, obvious approach. This is Step 6, so recon (Step 2) has already established the blast radius — the skip is evidence-based, not a guess; **record it** (one line in the plan / report) so an auto-mode mis-call is auditable. Any doubt, or anything above trivial → call it. advisor #2 (Step 12) runs regardless.

- Round cap: 3. If round 3 still surfaces new material — the approach is wrong; stop, escalate to user, do not run a 4th round.
- A critical advisor finding → revise plan / approach, re-call.
- A passed advisor → proceed.

### 7. Approval (interactive) / proceed (auto)

- **Interactive + plan file exists:** wait for `ExitPlanMode` approval. The approval is the execution authorization — no extra "when to start?" turn. `ExitPlanMode`'s `allowedPrompts` already captures the granted permissions.
- **Interactive + no plan file:** the synthesised plan is presented inline; proceed unless the user objects within the same turn.
- **Auto-mode:** proceed.

A casual "ok / sounds good" in regular chat is not a substitute for `ExitPlanMode` approval on a non-trivial change with a written plan. If a plan file exists in interactive mode, route through the gate.

### 8. Execution

Dispatch specialised sub-agents for the work itself — one per independent piece. In every execution prompt:

- **Path restriction** (same as Recon).
- **TDD — non-negotiable** for business logic, validators, lifecycle, calculations, bug fixes: explicit "write a failing test first, then minimal code, then refactor". Spike / exploratory code is exempt while the shape is still being discovered, but covered by a test before declare-done. See [`testing-strategy`](../testing-strategy/SKILL.md) for the tier and level decision.
- **Concrete `file:line` targets** — not "find and fix", but "edit `service.ts:120-145`, function `processOrder`, condition on line 132".
- **Anti-regression scope:** "do not change `<list of adjacent files>` even if you spot opportunities" — those are tickets, not edits.
- **Verification command:** "after the edit, run `<lint | typecheck | test>` and report the result".

Independent execution phases dispatch in parallel (one message, multiple `Agent` calls). Dependent phases run sequentially.

Specialised agents — pick by the project's stack. If the project has a `CLAUDE.md` listing specialised agents (e.g. `backend-python-developer`, `enterprise-react-developer`), use those. Otherwise dispatch a `general-purpose` sub-agent with explicit constraints.

### 9. Verification after each execution sub-agent

Do not trust the agent's "done" without verification:

- `grep` the changed file for the assertion the agent claims to have added / removed.
- Run the lint / typecheck / test command the agent was told to run; read the output, not just the exit code.
- Read the first 30 lines of changed files — catches surprise mass-rewrites and accidental file replacement.
- `find . -name ".claude" -type d 2>/dev/null` from the project root — sub-agents occasionally leak transient state directories; clean them.

Mismatch → targeted follow-up to the same agent with the specific gap, not "try again". Re-dispatch on the same target cap: 2.

### 10. Out-of-scope findings → ticket

Any problem the agent (or recon) found that is **not** being fixed in this change → ticket via [`surface-ticket`](../surface-ticket/SKILL.md) before declare-done. This covers adjacent bugs, anti-patterns, postponed refactors, partial implementations left in place. The decision to not fix now is the trigger.

Fixed inline within scope — no ticket. Trivially safe cosmetic fixes (typo in comment, single rename) may apply inline — say so afterwards.

When a finding rises to a hard **stop** rather than a ticket (an un-discussed business-logic change that needs the user's decision), follow the execution-phase rule in [Two phases](#two-phases).

### 11. Edge-case sweep (after implementation)

One pass over the changed files for missed scenarios — empty / null / boundary inputs, concurrent operations, error paths, partial state, timeouts, retries, idempotence. One round only. Findings → fix inline if in scope, or ticket via [`surface-ticket`](../surface-ticket/SKILL.md).

If a dedicated edge-case auditor sub-agent is available, dispatch it; otherwise sweep inline. Do not loop a second round on the same files — perfectionism amplifies and finds non-issues.

### 12. Advisor #2 (mandatory before declare-done)

Before declaring the task complete — `advisor()` once more on the finished result. One round; this is validation, not re-design. **This call is unconditional, with one guarded exception: a pure-mechanical edit** — typo, rename, comment, or formatting with zero logic — **may skip advisor entirely, but only when both guards hold:** the change touches no exported / public identifier (nothing external can consume it), **and** no instruction-bearing text (`CLAUDE.md`, a skill, or an agent definition — those change agent behaviour, so they are never "mechanical"). Fail either guard → advisor #2 runs.

If the advisor surfaces a new issue at this stage — verify it against the actual change. A finding the advisor missed during #1 but caught at #2 is worth fixing; a conflict between advisor and primary-source evidence is worth one reconcile call.

### 13. Git safety check (before destructive operations)

Before `git checkout <sha>`, `git reset --hard`, `git rebase`, `git push --force`, `git commit --amend` on shared commits, database `DROP`, mass `DELETE`, production migration, `rm -rf` with broad scope — stop and answer three questions:

1. Where am I now? (branch vs detached, working tree state, origin tracking)
2. Where will I be after the command? (new HEAD, dangling commits, recoverable via reflog / backup?)
3. Is the whole sequence safe end-to-end, not just this one command?

If any answer is not clear — do not execute. Surface to the user.

### 14. Commit via `git-conventional-commits`

When the change is ready and verified — invoke [`git-conventional-commits`](../git-conventional-commits/SKILL.md). It resolves the description language from the repo (explicit `CLAUDE.md` directive → existing commit history → English default), not from the conversation. English `type/scope/!` always, identifier names in backticks, body as bullet list, mixed changes split into atomic commits.

Never emit AI-attribution trailers (`Co-Authored-By: Claude …`, `Generated with Claude Code` and similar).

### 15. Push policy

- Feature / test / topic branches — may push without explicit per-session approval.
- `main` / `master` / any shared release branch — explicit per-session approval required.
- `--force` on a shared branch — never without explicit user request naming that branch by name.
- `--no-verify` — never.

### 16. Report to user

**Multi-phase task** (executed in stages): after each phase a short intermediate report; the next phase starts without asking unless there is a real fork (design choice, blocker, sensitive operation).

**Single-phase task** or **final report** — same shape, rendered in the user's language:

```
Done: 1-3 lines — what changed.
Verified: which commands / files — concretely.
Remaining: next phase / smoke / push / user dependencies.
Risks: what could break and how to roll back.
```

Style: plain language (the user's language), identifier names in backticks, no emoji unless asked, no "continue?" when the next step is obvious from the plan.

**Fill the plan file's "What actually happened" section** after the task lands. Deviations from plan, surprises, what cost more / less. This is the audit value of the plan file — not the plan itself, but the diff between plan and reality.

## Closing common rationalisations

| Excuse | Reality |
|---|---|
| "It's a small change, advisor isn't needed" | advisor #2 stays (bar a guarded pure-mechanical edit, Step 12); advisor #1 is skipped only on a **recon-confirmed** low-blast-radius change — decided after recon, recorded, never on the *feeling* that it's small. The gate is recon-established blast radius, not size. |
| "Urgent — skip verification" | Verification separates "agent said done" from "actually done". Urgency is reason to be careful, not careless. |
| "Obvious — recon isn't needed" | Most regressions start from confidence without recon. 3-5 files is 2 minutes. |
| "One file, no plan needed" | One file ≠ one phase. If the change has internal dependencies (data model → migration → service → tests), still ≥ 3 phases — plan file applies. |
| "I've done this before" | New context, new project state, new dependencies. Recon still runs. |
| "I'll do it faster than a sub-agent" | True for narrow targeted edits. False for broad investigation. Default to dispatch for anything multi-file or multi-angle. |
| "I'll write the test later" | Then the change is not done. TDD trigger fires on business logic and bugfixes — see [`testing-strategy`](../testing-strategy/SKILL.md). |
| "Urgent — plan file is overkill" | Plan file is 2 minutes; the audit trail it leaves saves hours when something breaks. Triggered by phases / edge-cases, not by urgency. |

## When the cycle does NOT apply

Read-only questions only:
- "What's in this file?"
- "How does X work?"
- "Where is Y?"
- "Explain the architecture of Z."

Anything that **changes** state — files, config, infra, database, deployment — runs the cycle.

## Stop conditions

| Loop | Max rounds |
|---|---|
| Advisor #1 (on approach) | 3 |
| Advisor #2 (final) | 1 |
| Edge-case sweep | 1 |
| Re-dispatch same agent on same target | 2 |

At the cap — stop, do not "keep improving". A loop hitting the cap is a signal the approach is wrong, not that one more round will close it.

## Cross-refs

- [`surface-ticket`](../surface-ticket/SKILL.md) — out-of-scope and postponed findings (Step 10).
- [`testing-strategy`](../testing-strategy/SKILL.md) — test level decision and Red → Green → Refactor (Step 8 TDD).
- [`code-audit`](../code-audit/SKILL.md) — parallel multi-aspect review (alternative to Step 11 edge-case sweep when the surface is broader).
- [`severity-calibration`](../severity-calibration/SKILL.md) — ranking findings honestly (used in advisor responses and reports).
- [`no-suppression-markers`](../no-suppression-markers/SKILL.md) — `TODO` / `FIXME` / `.skip` / disable-comment ban (active throughout — never the resolution to a found issue).
- [`ops-app-server-safety`](../ops-app-server-safety/SKILL.md) — when the work spawns dev servers or `docker compose` stacks (Step 8 verification of running processes).
- [`git-conventional-commits`](../git-conventional-commits/SKILL.md) — commit step (Step 14).
- [`web-search`](../../agents/web-search.md) — authoritative source verification (Step 2 Recon when Context7 misses or surfaces conflict).
- [`decision-reviewer`](../../agents/decision-reviewer.md) — adversarial grounded review of a high-stakes approach (Step 6a, before the advisor checkpoint; conditional on cost-of-wrong).
