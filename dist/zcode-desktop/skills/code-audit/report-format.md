<!-- Generated from MAINFRAME hub (core/skills/code-audit/report-format.md) — do not edit. -->

# Audit report format

Skeleton for the synthesized report. Numbering: `{DIM}-{NNN}` — e.g. `SEC-001`,
`ARC-001`, `PRF-001`, `BIZ-001`, `TST-001`.

## Header

- Title: `Code Audit: {target}`
- Date, scope (target path), previous audit (link or "first audit").

## Statistics

A severity table (Critical / High / Medium / Low / Total) and a dimension × severity
matrix, so the reader sees the shape at a glance.

| Severity | Count |
|----------|-------|
| Critical | X |
| High     | Y |
| Medium   | Z |
| Low      | W |
| Total    | N |

## Findings

Grouped by severity (Critical first). Each finding:

- ID: `{DIM}-{NNN}`
- Location: `path:line`
- Dimension
- What: the problem in one or two sentences
- Impact: what happens if it is left unfixed
- Recommendation: how to fix it
- Breaking change: yes / no

## What was done well

A short list of positive findings — patterns worth keeping and spreading. This calibrates
the reader and tracks progress between audits.
