---
id: 004
title: Hub-wide de-emphasis sweep — remove **bold** / CAPS emphasis from model-facing artifacts
status: open
priority: low
component: artifacts
discovered: 2026-06-12
discovered-from: []
tags: ["formatting", "prompting", "skills", "claude-md", "adr-0081"]
---

# 004: Hub-wide de-emphasis sweep — remove **bold** / CAPS emphasis from model-facing artifacts

## What was observed
Per ADR 0081 (verified on both the API prompt-engineering and CLI surfaces), `**bold**` and ALL-CAPS
emphasis on instruction keywords is NOT an adherence lever — Anthropic's own CLI artifacts avoid it, and the
API docs actively counter-indicate it ("replace 'CRITICAL: You MUST…' with normal prompting"; "avoid `**bold**`
and `*italics*`"). The hub's model-facing artifacts use such emphasis by habit. Fixed inline already:
`session-posture.py` POSTURE (`**BEFORE**`→`before`, `READ`→`read`). Remaining sites still carry emphasis —
e.g. POSTURE itself (`MODIFIES`, `STOP` caps), and `**bold**` runs in `task-workflow/SKILL.md` and likely other
skills / agents.

## Why it is a problem
Two concrete harms (ADR 0081): (1) over-formatting adds tokens without adherence gain; (2) prompt formatting
style bleeds into the model's reply style ("removing markdown from your prompt can reduce the volume of markdown
in the output") — which works against the user's standing demand for short, plain replies. Low severity (no
correctness impact), but it is a systematic style drift across authored
`core/` and `adapters/` artifacts and their rendered `dist/` projections.

## Why it is not a duplicate

[#b74495c2](b74495c2-decision-tree-stale-export-paths.md) owns architectural
path drift from `export/` / `plugin-dist/` to `core/` / `adapters/` / `dist/`.
This ticket owns prompt-style emphasis within model-facing artifacts; updating
its scope paths does not absorb the placement-documentation work.

## What probably needs to be done
- Sweep authored model-facing sources under `core/instructions/`,
  `core/skills/`, `core/agents/`, `core/gates/`, and tool-specific
  `adapters/` instructions/projections for `**bold**` and
  CAPS-emphasis-on-keywords. Render into `dist/` and use the rendered tree as
  a drift check; do not hand-edit generated output. Replace cosmetic emphasis
  with plain prose while keeping real structure (headers `##`, backticks for
  identifiers/paths, numbered/bulleted lists, XML where used).
- Do it as ONE deliberate pass (not opportunistically), so the diff is reviewable and the "what is structure vs
  what is cosmetic emphasis" judgement is consistent.
- Optional, for certainty beyond the docs: an `agent-tournament`-style empirical probe (instruction with vs
  without emphasis, measure following) before a large rewrite — only if the doc + practice evidence in ADR 0081
  is judged insufficient.

## Acceptance criteria
- No cosmetic `**bold**` / CAPS-keyword emphasis remains in authored
  model-facing sources; structural labels and semantic distinctions are
  retained.
- Rendered `dist/` outputs contain no cosmetic emphasis absent from their
  authored source.
- Validators still pass (`validate-skill.py`, `validate-claude-md.py`).
- A spot-check confirms meaning is preserved (emphasis removal did not drop a real semantic distinction).

## Progress (2026-06-15)

The **skills** half of this sweep was done during the skills/agents convention audit (session
b1c19a40). A 4-agent audit flagged emphasis (bold/CAPS) vs structural labels conservatively; a single
scoped pass removed the flagged emphasis across 16 affected skill sources in
the then-current `plugin-dist/skills/**/SKILL.md` layout
(decision-review, dokploy-api, frontend-design, git-conventional-commits, secrets-handling, shadcn,
surface-ticket, task-workflow, testing-strategy, no-suppression-markers, ops-app-server-safety,
code-audit untouched-for-emphasis, python/nestjs/nextjs/react-patterns). Structural labels
(`**Label.**` at list-item start, table headers, defined terms) were preserved; `validate-skill.py`
green; full `git diff` reviewed (no dropped words, links/backticks intact). Commit `style(skills)`.

**Remaining scope (still open, mapped to the current layout):**
- Umbrella instructions authored in `core/instructions/` and tool-specific
  refinements under `adapters/`.
- Hook posture/notes in `core/gates/detectors/session-posture.py` and their
  rendered `dist/` projections.
- `core/agents/*` bodies — the engineer agents' Discipline sections use `**Label:**` forms
  that read as structural labels (likely keep), but a deliberate pass should confirm none are
  emphasis. The cross-ref intros were already reframed (separate `fix(agents)` commit).

The judgement applied: the skills pass treated `**Label.**`-at-line-start as structural (kept) and
mid-prose `**bold**` / CAPS-for-stress as emphasis (removed). Apply the same rule to the remaining
surfaces for a consistent diff.

## Re-measurement (2026-07-28)

The sweep is still needed. A raw search for `**…**` over Markdown, Python,
JavaScript, and shell artifacts found 657 matches under `core/`, 50 under
`adapters/`, and 743 under generated `dist/`. These are candidate counts, not
violation counts: many are structural labels and must remain. Separately,
`core/gates/detectors/session-posture.py` still uses `MODIFIES` and `STOP` for
stress, and the same text appears in the Claude Code render, proving at least
one unambiguous CAPS-emphasis remainder.

## Sources
- `docs/decisions/0081-artifact-prompting-style.md` (the standard + both-surface evidence).
- `core/gates/detectors/session-posture.py` — current authored POSTURE source.
- `core/instructions/`, `core/skills/`, `core/agents/`, `core/gates/`, and
  `adapters/` — current authored scope; `dist/` is the generated verification scope.
- Skills half: session b1c19a40 (2026-06-15), commit `style(skills)` in the
  then-current layout.
