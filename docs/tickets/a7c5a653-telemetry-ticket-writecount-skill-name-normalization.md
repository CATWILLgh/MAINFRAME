---
id: a7c5a653
title: "Telemetry: ticket_created is a write-count, and skill_load names are unnormalized"
status: closed
priority: medium
component: hooks
discovered: 2026-06-08
discovered-from: []
tags: ["telemetry", "measurement-integrity", "analytics"]
---

# a7c5a653: Telemetry — ticket_created is a write-count, and skill_load names are unnormalized

## What was observed

First telemetry pass (2026-06-04 → 06-08) surfaced two payload-interpretation defects:

1. **`ticket_created` counts `PostToolUse(Write)` events to `docs/tickets/`, not distinct tickets.** The file path is deliberately not logged (privacy), so a ticket that is written, then resolved, then audited via `Write` logs **3 events for 1 ticket**. Observed: 145 events, 109 of them in one project (`IISHNITSA`) — almost certainly inflated by rewrites/resolutions, not 145 distinct tickets.
2. **`skill_load` records the skill name in two forms** — `mainframe:task-workflow` (9) vs `task-workflow` (4), `mainframe:surface-ticket` (5) vs `surface-ticket` (2), same for `git-conventional-commits`. The same skill splits across two buckets depending on how it was invoked (namespaced vs bare).

## Why it is a problem

Both distort the very metrics the layer exists to drive (decision-linkage, ADR 0073):
- `ticket_created` is meant to feed the **ticket-vs-incident ratio** ("is the surface-ticket discipline landing?"). A write-count can't answer that cleanly — it's an upper bound conflating creation with rewrite.
- `skill_load` aggregation under-counts per-skill usage because one skill lands in two name buckets — the "which discipline is actually invoked" read is split.

Measurement integrity is the whole point of the telemetry layer; a metric that silently over- or mis-counts is worse than none.

## Why it is not a duplicate

- [faa110d8](faa110d8-telemetry-detector-incident-wiring.md) and [40654275](40654275-telemetry-enable-canblock-events.md) add new event **sources**; this ticket is about **interpreting / normalizing existing payloads**. No overlap.

## What probably needs to be done

**ticket_created** — pick one:
- (a) Accept it as a write-count and document in ADR 0073 / analytics notes that it is an upper bound (interpret accordingly); OR
- (b) Add a privacy-safe distinct-ticket signal — e.g. log a **salted hash of the ticket basename** (not the path, not the body) so create-vs-rewrite can be de-duplicated without storing identifying path data. (Requires verification that the basename hash carries no sensitive info — ticket slugs can be descriptive; a per-install salt mitigates.)

**skill_load** — normalize the name: strip the plugin namespace prefix (`mainframe:` / any `<plugin>:`) before logging, or store both `raw` and `normalized`, so one skill = one bucket. Update the `skill_load` branch in `telemetry.py`.

Update any analytics queries to match the chosen semantics.

## Acceptance criteria

- `ticket_created` semantics either documented as a write-count (option a) or de-duplicated to distinct tickets (option b), with the privacy property re-verified if a hash is added.
- `skill_load` skill names normalized so the same skill aggregates into one bucket; verified against a fresh sample.
- The unit-test privacy assertion (`tools/test_telemetry.py`) still passes — no banned keys, and any new hash carries no path/body.

## Sources

- `plugin-dist/hooks/scripts/telemetry.py` — `_ticket_component` (PostToolUse Write branch, line ~58-61) and the `skill_load` branch (line ~55-57).
- `~/.claude/telemetry/telemetry.db` — `ticket_created` / `skill_load` rows.
- ADR 0073 (telemetry design + decision-linkage table).

## Resolution (2026-06-08)

**Implementer:** main session (telemetry first-pass follow-up; uid approach suggested by the user).
**Commits:** b7f0f74
**Summary:** Chose option (b) for ticket_created — `uid = sha256(basename)[:12]` is logged alongside `component`, so distinct tickets count via `COUNT(DISTINCT uid)` and create-vs-rewrite is separable, with the descriptive slug and path never logged (privacy intact). skill_load now normalizes the name (`_norm_skill` strips the `<plugin>:` namespace), so `mainframe:task-workflow` and `task-workflow` aggregate into one bucket. Extracted pure helpers `_ticket_uid` / `_norm_skill`.

**Claims to verify on audit:**
- `tools/test_telemetry.py` → 7/7 pass, including `test_ticket_uid_is_hash_not_slug` (uid is 12 hex chars; the slug and id are absent; stable per file → rewrite shares uid; distinct ticket → distinct uid) and `test_skill_name_normalized`.
- Integration probe: feeding `telemetry.py` a `PostToolUse` Write to a ticket whose basename contains a secret slug logs `{component, uid}` with the slug AND path absent from the stored row (`grep` over the DB is clean).
- `skill_load` for raw `mainframe:task-workflow` stores `skill: task-workflow`.

> Note: the existing 145 `ticket_created` rows pre-date this change and carry no `uid` — distinct-ticket counting applies to rows logged from b7f0f74 onward.
