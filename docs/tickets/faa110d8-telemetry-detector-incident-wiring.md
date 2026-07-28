---
id: faa110d8
title: Wire incident telemetry into the detector/gate hooks (per-rule FP tracking)
status: open
priority: medium
component: hooks
discovered: 2026-06-04
discovered-from: []
tags: ["hooks", "telemetry", "analytics", "security-gates", "tech-debt"]
---

# faa110d8: Wire incident telemetry into the detector/gate hooks (per-rule FP tracking)

## What was observed

ADR 0073 shipped the telemetry core (`_hooklib.log_event` + `telemetry.py` on 6 events) but **deliberately did NOT** wire the `incident` event into the ~11 detector/gate hooks. The `incident` metric (FP-rate-per-rule → tune/retire a rule) is the one with the sharpest decision-linkage in the ADR table, and it is the only one whose data source is the detectors themselves.

It was deferred because: (a) it is **22 edits across 11 working, tested security/quality gates** (an `import` + a `log_event` line each) — the highest-blast-radius surface (advisor #2 flagged it as THE regression surface); and (b) to deliver per-*rule* FP (not just per-*hook* count) each gate needs detector-specific rule-extraction, which is more than a one-liner.

## Why it is a problem

Without it, `ticket_created vs incident` ratio (a key Bucket-1 "does the agent walk past problems" signal) is uncomputable, and there is no FP/noise data per rule to drive hook curation. It is the most decision-linked metric and currently uncollected.

## Why it is not a duplicate

[#40654275](40654275-telemetry-enable-canblock-events.md) is about registering
the already-implemented `turn`, `subagent_stop` and `compaction` handlers only
after their empty-output contracts are proven safe. [#e5308bd1](e5308bd1-opencode-telemetry-source-tag.md)
is about tagging event origin and delivering telemetry from OpenCode. This
ticket requires new detector-side `incident` emission and per-rule payload
design across the gate inventory; neither event registration nor source
tagging supplies that data.

## What probably needs to be done

- For each detector (`scan-suppression-markers`, `comment-discipline-reminder`, `python-security-scan`, `nodejs-security-scan`, `python-deps-audit`, `nodejs-deps-audit`, and the Stop gates `stop-gate-suppression-markers`, `python-security-stop-gate`, `nodejs-security-stop-gate`, `frontend-fsd-gate`, `frontend-dead-code`): add `log_event("incident", {...}, payload)` **after** the FINDINGS emit (not the install-hint emit) so a telemetry failure cannot touch the gate's decision/emit path.
- Payload: at least `{hook, count, file_ext}`; ideally `rule_id` per finding (detector-specific extraction — the ruff/semgrep code, the marker type, etc.) for per-rule FP.
- Import `log_event` into each detector's `from _hooklib import …` line.

## Acceptance criteria

- Per gate: `git diff` shows ONLY the added import + the added `log_event` line; the gate's existing probe re-runs **identical** (decision path byte-identical).
- `incident` rows appear in the telemetry DB with `{hook, count[, rule_id]}` when a detector finds something; nothing logged on the install-hint path.
- No gate's security/quality behaviour changes.

## Sources

- ADR 0073 — `docs/decisions/0073-telemetry-layer.md` (deferral + decision-linkage table).
- Emit sites mapped: `grep -nE 'emit_note\(|emit_block\(' plugin-dist/hooks/scripts/*.py`.
