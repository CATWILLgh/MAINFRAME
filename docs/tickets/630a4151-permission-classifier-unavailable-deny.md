---
id: 630a4151
title: "Auto-mode 'Classifier unavailable' denies Bash — identify source + failure mode"
status: open
priority: low
component: permissions
discovered: 2026-06-08
discovered-from: []
tags: ["permissions", "auto-mode", "telemetry-finding", "reliability"]
---

# 630a4151: Auto-mode "Classifier unavailable" denies Bash — identify source + failure mode

## What was observed

First telemetry pass (663 events, 2026-06-04 → 06-08) — of 18 `permission_denied` events, **9 carried `reason = "Classifier unavailable"`**, and all 9 are concentrated in **one session of one project** (`IISHNITSA`). The other 9 denials are genuine policy stops (prod env read, `/dev/urandom`, shared-PostgreSQL restart, out-of-project script exec, etc.).

```
SELECT reason, count(*) FROM events
WHERE event='permission_denied' GROUP BY reason;
-- "Classifier unavailable" -> 9   (1 project, 1 session)
```

## Why it is a problem

When the auto-mode permission classifier is "unavailable", the command is **denied by default**. In auto-mode (the hub's primary workflow — hours-to-days autonomous runs), a transient classifier failure silently blocks legitimate `Bash` and stalls the run. The concentration in a single session says this is **transient / localized, not systemic** — hence low priority — but the failure mode (default-deny on classifier-down, with no degraded path) is worth understanding before it bites a long unattended run.

## Why it is not a duplicate

- [faa110d8](faa110d8-telemetry-detector-incident-wiring.md) — wiring detector `incident` events; unrelated.
- [40654275](40654275-telemetry-enable-canblock-events.md) — enabling can-block telemetry events; unrelated.
Neither concerns the permission classifier's reliability or its deny-on-failure behaviour.

## What probably needs to be done

1. **Identify the source of `"Classifier unavailable"`** (requires verification): is it the Claude Code harness's own auto-mode permission classifier, or a hub-side hook? The string looks harness-internal — confirm via `claude-code-guide` / bundle inspection before assuming a hub fix.
2. If harness-internal: the hub cannot fix the classifier, but **can pre-empt** the deny by adding allow-rules in `settings.json` for the specific safe commands that were denied (so a classifier outage doesn't block them). Weigh against the deny-by-default safety posture.
3. If hub-side: find why it was unavailable (missing dep / timeout / cold start) and decide whether default-deny is the right failure mode, or degrade to ask / allow-with-log for low-risk commands.
4. Re-check the next telemetry pass — if "Classifier unavailable" stays a single-session blip, downgrade to won't-fix-documented.

## Acceptance criteria

- Source of `"Classifier unavailable"` identified (harness vs hub) with evidence.
- A documented decision on the deny-on-classifier-failure behaviour (accept / pre-empt with allow-rules / degrade).
- If a fixable hub reliability bug — fixed and verified; otherwise documented as a CC limitation with the chosen work-around.

## Sources

- `~/.claude/mainframe/telemetry/telemetry.db` — `permission_denied` rows (path moved 2026-06-11, ADR 0076).
- Memory: `permissions-auto-mode-classifier` (auto-mode 4-step classifier; ask→defer in auto-mode).
- `export/settings.json` permission tiers.
