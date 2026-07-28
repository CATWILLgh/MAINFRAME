---
id: d84dc65e
title: code-audit dimensions.md doesn't explicitly name STRIDE/taint/SOLID-per-letter/TOCTOU/DTO-OpenAPI-drift
status: open
priority: low
component: skills
discovered: 2026-07-06
discovered-from: []
tags: ["code-audit", "documentation", "review-quality"]
---

# d84dc65e: code-audit dimensions.md doesn't explicitly name STRIDE/taint/SOLID-per-letter/TOCTOU/DTO-OpenAPI-drift

## What was observed

Recon (2026-07-06, during the length-gate hook task) checked `plugin-dist/skills/code-audit/dimensions.md` against a broader review-dimension catalog (OWASP API Top 10, STRIDE, SOLID per-letter, TOCTOU, data-flow/taint tracing, DTO/OpenAPI/schema-migration contract drift). Result:

| Dimension | Present? |
|---|---|
| STRIDE / threat modeling | Absent (security section has injection/authn/secrets/validation, no STRIDE framing) |
| SOLID (OCP/LSP/ISP/DIP/SRP) | Partial — bare word "SOLID" only, no per-letter breakdown (`dimensions.md:18`) |
| Race condition / TOCTOU | Partial — "race conditions" named, no TOCTOU term (`dimensions.md:31`) |
| Data-flow / taint tracing | Absent as a named technique |
| API contract drift (DTO↔OpenAPI, schema↔migration) | Partial — generic "inconsistent API contracts" only, no DTO/OpenAPI/migration-drift language (`dimensions.md:33`) |

`dimensions.md:5` and `SKILL.md:27-29` already frame the five categories as "the floor, not the ceiling" — so these are not hard misses (an auditor can still report them under the existing categories), only unnamed ones.

## Why it is a problem

Per the hub's own CLAUDE.md rule on anti-patterns ("name the pattern using established terminology... established terminology improves detection"), explicitly naming a known framework (STRIDE, TOCTOU, per-letter SOLID) in review instructions plausibly raises an auditing agent's recall for that class of issue, versus leaving it implicit under a generic "floor not ceiling" catch-all. Unverified assumption — see Acceptance criteria.

## Why it is not a duplicate

No existing ticket covers `code-audit` dimension coverage. User explicitly deferred this ("попозже" / "later") during the 2026-07-06 hook-vs-LLM-review-boundary conversation — this ticket exists so the deferred item isn't lost, per the hub's ticket-discipline rule (a decision to not fix now is the trigger to ticket, not to silently drop).

## What probably needs to be done

Requires verification before editing `dimensions.md` (do not add speculatively — hub's "provable necessity" principle):
1. Confirm whether naming these terms explicitly measurably changes audit recall (small before/after experiment: same seeded-flaw fixture, one run with current dimensions.md, one with named additions, compare recall) — or accept it on the authoritative-terminology-improves-detection reasoning already codified in CLAUDE.md's anti-pattern-naming rule, without a fresh experiment, if that rule is judged to already cover this case.
2. If proceeding: add explicit terms to `plugin-dist/skills/code-audit/dimensions.md` without expanding scope — a few added nouns per existing category (STRIDE, TOCTOU, SOLID per-letter, taint, DTO/OpenAPI drift), respecting the skill's line-count budget (ADR 0003: 500 lines / 5K tokens for `SKILL.md`, 60 lines / 5K tokens per supporting file — check `dimensions.md`'s current length against that cap before adding).

## Acceptance criteria

Either: (a) a small measured experiment showing a recall difference, with the addition made and cited; or (b) an explicit decision to add the terms anyway citing the existing CLAUDE.md anti-pattern-naming rule as sufficient justification without a fresh experiment; or (c) an explicit decision NOT to add them, with reasoning recorded here. Any of the three closes this ticket — the point is a recorded decision, not a mandated edit.

## Sources

- `plugin-dist/skills/code-audit/dimensions.md` — current dimension list.
- `plugin-dist/skills/code-audit/SKILL.md:27-29` — "floor not ceiling" framing.
- `docs/principles.md` §2 — "provable necessity" (don't add without evidence).
- `export/CLAUDE.md` — anti-pattern naming rule ("name the pattern using established terminology").
- `tools/validate-skill.py` / ADR 0003 — line/token budget for skill supporting files.
