---
id: 5fae0bfa
title: OpenCode-tuned AGENTS.md — CC-flavored CLAUDE.md text runs on GLM-5 with dead tool references
status: closed
priority: medium
component: opencode-layer
discovered: 2026-07-08
discovered-from: []
tags: ["opencode", "claude-md", "instructions"]
---

# 5fae0bfa: OpenCode-tuned AGENTS.md — CC-flavored CLAUDE.md text runs on GLM-5 with dead tool references

## What was observed
OpenCode reads `~/.claude/CLAUDE.md` as its global rules fallback (no
`~/.config/opencode/AGENTS.md` exists — phase 1 deliberately did not add one).
The hub's `export/CLAUDE.md` is dense with Claude-Code-only machinery: the
advisor checkpoint, `mainframe:` agent dispatch, hooks, `AskUserQuestion`,
`TodoWrite`, Context7 MCP tool names. In OpenCode sessions this text drives
GLM-5, where those tools do not exist.

## Why it is a problem
Decision-review 2026-07-08, objection 5: instructions referencing absent
tools become dead directives at best, hallucination-inducing at worst ("call
advisor before substantive work" has no possible compliance path). The
behavioural core (honesty, evidence, engineering rules) transfers fine; the
tool-bound sections do not.

## Why it is not a duplicate
[#001](001-agents-md-stale-plugin-migration.md) concerns the repo's own
stale docs about plugin migration, not OpenCode instruction delivery. No
other ticket covers OpenCode.

## What probably needs to be done
1. Decide the mechanism first (this is the fork): (a) a GENERATED
   `~/.config/opencode/AGENTS.md` — `build_opencode.py` strips/rewrites
   CC-only sections from `export/CLAUDE.md` (keeps single-source, adds a
   fragile text transform); (b) a hand-maintained OpenCode preamble that
   `@`-includes or links the shared core (clearer, but a second instruction
   file to maintain); (c) restructure `export/CLAUDE.md` itself into
   tool-agnostic core + CC-specific sections so a projection becomes a clean
   section filter. Option (c) aligns best with hub principle 4 but is the
   most invasive — needs its own decision-review.
2. Verify on the installed OpenCode which files load together (global
   AGENTS.md vs ~/.claude/CLAUDE.md fallback vs project files) to avoid
   double-loading.
3. Measure before building: capture 2-3 real OpenCode/GLM-5 transcripts and
   check whether dead references actually mislead the model (the objection is
   plausible but unquantified — hub principle 2 wants evidence before build).

## Acceptance criteria
- An OpenCode session's loaded instructions contain no references to tools
  that do not exist in OpenCode (verified via `opencode debug` / transcript).
- Single-source: whatever ships is generated or filtered from hub sources,
  not a hand-copied fork of CLAUDE.md.

## Sources
- https://opencode.ai/docs/rules/ — AGENTS.md preference, CLAUDE.md fallback
- Decision-review 2026-07-08, objection 5
- `export/CLAUDE.md` — Advisor / Orchestration / Verification sections (CC-bound)
- `docs/reference-mining/D-opencode-parallel.md` §5 («скилл скиллу рознь»)

## Re-occurrence noted (2026-07-08)

**Noticed during:** ADR 0085 agents slice, reviewer #2 validation pass
**Where:** `core/agents/devops-engineer.md` body (rendered verbatim into the
OpenCode agent) — asserts a background-run / destructive-op-approval runtime
guarantee that Claude Code enforces but OpenCode's permission model may not
(`ask` degrades under `--auto`).
**Additional details:** same class as this ticket's subject — CC-runtime
assumptions inside prose delivered to OpenCode. Agent BODIES are passed
through verbatim by design in wave 1; prose neutralization is the deferred
follow-up where this instance should be resolved.

## Partial resolution note (2026-07-09)

The three FALSE-safety claims are fixed at the source (`core/agents/
devops-engineer.md` 20-22/43/90): "auto-denied" is now a runtime-conditional
parenthetical, the "`ask`-gated ⇒ defers" inference is replaced by an
unconditional never-execute rule, "(background mode cannot confirm)" became
"(an unattended run cannot confirm)". CC render, OC golden and deployed OC
agent regenerated.

Scope decision (prose review, proceed-with-adjustments): CC tool NAMES in
skill/agent prose (`Explore`, `Agent`, `TodoWrite`, plan-mode tools) stay —
they are honest on Claude Code and dead-but-not-false on OpenCode, renaming
them does not make the multi-agent process true there, and
`task-workflow`'s body sits at 4998/5000 tokens (2-token headroom). The
real fix remains this ticket's subject: a composed per-tool render once an
OpenCode skills-delivery surface is designed.

## Re-occurrence noted (2026-07-10)

**Where:** `core/agents/devops-engineer.md` body — a bullet explaining the CC
frontmatter choice ("`model: opus` / `effort: high` — set for the deeper
infra-reasoning profile…") ships verbatim to OpenCode, where the enriched
model is actually `openai/gpt-5.6-sol`. Same class: prose explaining one
tool's dialect delivered to another tool.

## Resolution (2026-07-13)

**Implementer:** engineering session (task-workflow).
**Commits:** `d7864e65384e216fe7718caf06ccf939d903859d`,
`ee64d38c0f6b2a7ad915c22efbaf80f5fb0d6813`.
**Summary:** The two layers this ticket spans are now resolved.

*Instructions layer (`export/AGENTS.md`):* already at its accepted state. The
hard `advisor` directive is REPLACED by OpenCode runtime notes (adapter
`90-runtime-opencode`: "there is no `advisor` tool — dispatch `decision-reviewer`"),
not merely deleted. The residual `AskUserQuestion` / `Explore` references are
dialect-tagged ("Claude Code: `X`") and stay per the recorded 2026-07-09 scope
decision (dead-but-not-false — naming the CC tool does not make the process
true on OpenCode, and renaming does not help). `Context7` is NOT a dead
reference: it resolves on OpenCode (a subagent live-enumerated
`context7_resolve-library-id` / `context7_query-docs`, 2026-07-13). So
acceptance #1, read strictly, holds: no reference points at a tool absent on
OpenCode.

*Agent-body layer (this change):* removed the model/effort-provenance prose
from all 6 delivered bodies (5 engineers + `decision-reviewer`'s HTML comment).
It was maintainer meta — noise on Claude Code, and FALSE on OpenCode (it named
`opus`/`sonnet` and "tournament-calibrated", none true for the OC fleet
`glm-5.2`/`M3`/`gpt-5.6-sol` assigned by strength). Provenance confirmed
preserved BEFORE deleting: react in ADR 0062; python + nestjs in ADR 0063;
decision-reviewer in ADR 0065; nextjs in ADR 0074 + ticket 3aa0e17a; devops
migrated into ticket `35b82ec7` (its body bullet was the sole record). The
"re-tournament after a prompt-body change" trigger lives in the
`agent-tournament` skill, not the prompt.

**Live status (honest scope, mirrors the plugin fix):** source-neutralized and
render/golden-verified. The Claude-Code side is live via `plugin-dist` symlink.
The OpenCode side is NOT yet live in the user's `~/.config/opencode/agents/` —
those are GENERATED at install time (they carry the machine-local enrich, so
they cannot be symlinks), so the old bullets persist there until a user-gated
`./install.sh --opencode` re-run.

**Claims to verify on audit:**
- No agent BODY (core / plugin-dist / OC goldens) contains model/effort
  provenance prose (`rg 'Model \+ effort|model: opus|seeded-flaw'` → empty).
- `python3 tools/render_core.py --check` in sync; `test_build_opencode.py`
  14/14 (goldens match); `test_render_core.py` 35/35.
- devops provenance is recorded in `35b82ec7`; the ticket's item-2 config line
  reads `opus/high` (superseded in place, not appended-alongside).
