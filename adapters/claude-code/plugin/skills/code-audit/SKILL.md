---
name: code-audit
user-invocable: false
description: Run a structured, multi-aspect code and quality audit of a module, directory, or diff. Splits the audit into independent dimensions (security, architecture, performance, business logic, testing) run as parallel subagents, then deduplicates, verifies high-severity findings, and produces one prioritized report with a precise location per finding. Calibrates severity via the `severity-calibration` skill.
when_to_use: Trigger when a task involves auditing or reviewing quality of a module/directory/diff, finding problems after a refactor, or assessing architecture, security, or performance of a code region. Signal phrases include "audit X", "review quality", "find problems", "check the module", "assess Y", "where are our problems in X". Also runs proactively after a large refactor or feature lands.
---

# Code audit

A structured, multi-aspect audit of a codebase region. Output: one deduplicated,
severity-ranked report with a precise location for every finding.

## When to run

- The user asks to audit / review quality / find problems / assess a module.
- Proactively after a large refactor or feature — offer it, even unprompted.

## Workflow

### 1. Scope

Identify the target (directory, module, or diff) and the focus (full audit or specific
dimensions). If the target is not given, ask; if it is, start without re-asking.

### 2. Dispatch one subagent per dimension (parallel)

First read [dimensions.md](dimensions.md) — it holds the five audit dimensions with a
per-dimension checklist; load it every run, do not dispatch from memory. The five:
security & resilience, architecture & clean code, performance & data, business logic & API,
testing & observability. Launch one parallel `Explore` subagent (the built-in read-only
search agent) per dimension in a single message, each scoped to the target. Give each the
exact path and require this finding format:

- Location: precise `path:line`
- Severity: critical / high / medium / low
- What: one sentence
- Why: one or two sentences on the impact

Instruct each subagent: produce one entry per concrete finding (location + severity + what + why).
If a useful observation lacks a specific location (general design note, cross-cutting pattern),
include it under a brief "Notes" section at the end, kept separate from located findings.
Also flag any standout strengths (well-built patterns worth keeping) in their own short section.

### 3. Verify framework claims against current docs

For any "best practice" claim that depends on a framework or library, confirm it against
current documentation (Context7), not memory — versions drift. Findings that don't depend on
a library's behavior need no doc check.

### 4. Synthesize

- **Deduplicate** — one problem = one entry, even if several subagents reported it.
- **Verify critical/high** — re-read the location for each top-severity finding; drop false
  positives, lower partially-confirmed ones. Hallucinated criticals are unacceptable.
- **Assign severity** using the `severity-calibration` skill (its rubric and discipline). Do not inflate.
- **Collect strengths** — gather the standout strengths subagents flagged, for the "what was done well" section.
- **Count** — totals per severity and per dimension.

### 5. Report

First read [report-format.md](report-format.md) — the report skeleton (statistics tables, the
`{DIM}-{NNN}` finding fields, the "what was done well" section); load it every run. The report
carries: statistics (a severity table + a dimension × severity matrix), findings grouped by
severity (each with location, impact, recommendation), and what was done well.

### 6. Next steps

Propose a fix path proportional to the finding count — a quick pass for a small set, a phased
plan for a large one. Offer the choice; do not impose it.

## Principles

- **Facts, not guesses.** Every finding is backed by a concrete `path:line`. Unverified → flag and verify, don't ship it.
- **No duplicates.** One problem, one entry, even if found from several angles.
- **Honest severity.** Calibrate via `severity-calibration`; inflating critical devalues the real ones.
- **Verify, don't recall.** Check current docs for best-practice claims; don't trust memory on versions.
- **Note the positives.** Record what is done well — it calibrates the reader and shows progress between audits.
- **Reproducibility.** A finding must let another developer locate it, see why it is a problem, and know the fix.
