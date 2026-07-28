---
id: 74beb0fb
title: Stop-gate emulation for OpenCode via session.idle + client message injection
status: closed
priority: medium
component: opencode-layer
discovered: 2026-07-08
discovered-from: ["#b7a493b8"]
tags: ["opencode", "hooks", "stop-gate", "research"]
---

# 74beb0fb: Stop-gate emulation for OpenCode via session.idle + client message injection

## What was observed
OpenCode has no blocking turn-end mechanism: `session.idle` is notify-only,
and the `permission.ask` plugin hook does not fire (verified 2026-07-08 on
1.17.15). So the hub's Stop-gates (`stop-gate-suppression-markers`,
`stop-gate-comment-discipline`, `python/nodejs-security-stop-gate`,
`frontend-fsd-gate`) — the enforcement teeth — remain Claude-Code-only after
the dispatcher port.

## Why it is a problem
In CC a Stop-gate is un-ignorable: the model cannot end the turn with
unresolved findings. In OpenCode the same findings arrive only as advisory
notes the model may discount — thinner enforcement on the user's autonomous
runs.

## Why it is not a duplicate
[#b7a493b8](b7a493b8-opencode-plugin-port-security-hooks.md) covers the
before/after dispatcher (done); this is the deliberately deferred "deeper"
mechanism (user: локальный API применять осознанно, «глубже потом»).

## What probably needs to be done
1. PROBE FIRST (all unverified): on `session.idle`, can the plugin use the
   context `client` SDK to send a message into its own session, and does the
   model then continue working on it? What exactly does the message look like
   to the model?
2. Design the guard against loops (analog of CC `stop_hook_active`): run
   checks once per idle, re-nudge at most once until the finding set changes.
3. Run the same Stop scripts (they take `{stop_hook_active, cwd}` stdin) via
   the dispatcher's spawn machinery; translate `{"decision":"block","reason"}`
   into the nudge text.
4. Weigh honestly: a nudge is ignorable — decide whether partial enforcement
   is worth the added machinery, or whether waiting for a native blocking
   mechanism upstream is better. Desktop-app extra: `tui.toast.show` to
   surface findings to the human in parallel.

## Acceptance criteria
- A probe transcript showing the injected nudge arriving and the model
  resuming work (or a documented negative result closing this as not-viable).
- No idle-loop: two consecutive idles with an unchanged finding set produce
  no third nudge.

## Sources
- https://opencode.ai/docs/plugins/ — events catalog, client in context
- Probes 2026-07-08 (1.17.15): `permission.ask` dead; advisory channel works
- `plugin-dist/hooks/scripts/stop-gate-*.py`, `_hooklib.py` `stop_guard_cwd`

## Research findings (2026-07-08, autonomous run)

Per opencode.ai/docs/plugins/ + docs/sdk/ and upstream issue
anomalyco/opencode#16626:
- `session.idle` fires when the agent finishes a turn; plugins receive an SDK
  `client` with `session.prompt({path:{id}, body:{parts,…}})` — an
  idle→inject loop IS constructible with documented primitives today.
- BUT: the injected prompt surfaces as a visible user message (no silent
  stderr channel like Claude Code Stop hooks); re-prompting from idle races
  process teardown under `opencode run` (empty continuation turns); an
  unguarded re-prompt loops forever — any emulation needs a one-shot guard
  keyed to the finding set (re-fire only when findings CHANGE).
- A native `session.stopping` hook (stop=false + message re-entry, the clean
  analog) is an OPEN unmerged feature request (#16626) — not shipped.

**Decision:** defer implementation until `session.stopping` ships or the
visible-message tradeoff is explicitly accepted; when implemented, the design
is: subscribe `session.idle` → run the two security stop-gate detectors on
the session's changed files → if findings differ from the last injected set,
inject ONE summary prompt (sentinel in plugin state prevents repeats).

## Resolution (2026-07-13)

**Implementer:** engineering session (task-workflow).
**Commits:** f5151a6.
**Summary:** Implemented in `adapters/opencode/plugins/mainframe-gates.js` as an
`event` hook on `session.idle` (folded into the dispatcher — reuses its spawn
machinery). Runs the 5 stop-gate detectors over the session repo's
`git diff HEAD`, aggregates ALL findings into ONE labeled nudge
(`client.session.prompt`, "⚙️ [mainframe auto-check]") plus one human toast
(`client.tui.showToast`). Anti-loop: re-nudge only on a changed finding set,
capped at MAX_NUDGES=3; a fully-clean scan deletes the per-session key
(re-arm + map bound); a `git diff --quiet HEAD` precheck skips zero-change
turns. Delivery correctness relies on the host's per-instance directory filter
(`plugin/index.ts:252`) — the scanned `directory` is the idling session's repo.

**Decision path:** probe first (acceptance #1) confirmed injection lands in the
desktop app and the model resumes; the visible-message tradeoff was accepted
with honest labeling; the model-nudge scope was WIDENED to all gates
(CC-parity) per the user over the reviewer's security-only recommendation.

**Acceptance:**
- #1 (probe transcript, nudge arrives + model resumes) — MET: live desktop test,
  the model fixed the seeded S307 (`eval` → `ast.literal_eval`).
- #2 (no idle-loop) — MET by design + 40 node tests (unchanged finding set →
  no re-nudge; MAX_NUDGES cap) and demonstrated live by convergence-on-fix. The
  strict "model ignores, unchanged set" path is unit-covered, not yet observed
  live.

**Honest limits / follow-ups:**
- Ships live in EVERY project on the next OpenCode restart (symlinked plugin,
  no `install.sh` gate) and nudges on pre-existing uncommitted findings
  (whole-cwd `git diff HEAD`, CC-parity) — surfaced to the user.
- Headless `opencode run` cannot deliver the nudge (fire-and-forget teardown
  race #16879) — desktop-only by design.
- File length + event-handler complexity → ticket `057688a7`.
- The WIDENED (all-gates) version was unit-tested but not re-run live; the
  mechanics are identical to the live-verified security path.
