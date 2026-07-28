---
id: b86bf383
title: Codex gates v1 follow-ups — verify best-effort behaviors and tighten matchers
status: open
priority: medium
component: codex-layer
discovered: 2026-07-14
discovered-from: []
tags: ["codex", "gates", "hooks", "verification", "perf"]
---

# b86bf383: Codex gates v1 follow-ups — verify best-effort behaviors and tighten matchers

## What was observed
The Codex gates layer shipped 2026-07-14 (`adapters/codex/gates/mainframe-hook.sh` +
`GATE_HOOKS` in `adapters/codex/build_codex.py` → `dist/codex/hooks.json`). Probing
confirmed the blocking path end-to-end: Codex honors a stdout `permissionDecision:"deny"`
and blocks the tool. Several adjacent behaviors were shipped as best-effort with honest
caveats rather than verified, and one deliberate inefficiency was accepted:

1. **Advisory injection unverified** — whether Codex surfaces a hook's non-blocking
   `hookSpecificOutput.additionalContext` (to the model) and `systemMessage` (to the
   user). All PostToolUse advisory detectors depend on this.
2. **`"ask"` verdict unverified in `approval_policy=never`** — `path-validation.py`
   returns `permissionDecision:"ask"` (not `deny`) for e.g. `rm -rf` outside the project.
   Only `deny` was observed to hard-block. How Codex treats `ask` in headless auto-mode
   (prompt? proceed? block?) is unknown.
3. **Stop-block continuation unverified** — whether a Stop hook `{"decision":"block"}`
   forces the model to keep working (CC behavior) or merely nudges (OpenCode behavior).
   Only that Stop *fires* was confirmed.
4. **Matcher over-approximation (perf)** — every event group uses `matcher: ".*"`, so all
   of an event's detectors spawn on every matching tool call; detectors self-filter for
   correctness, but this is more python spawns per call than CC's per-tool matchers. Related:
   `mainframe-hook.sh` spawns a SECOND `python3` per hook just to extract `cwd` from the payload
   (to set `CLAUDE_PROJECT_DIR`, which Codex omits) — a cheaper structural extraction (or a Codex
   env var carrying the project dir, if one exists) would halve the python spawns.
5. **Telemetry + session-lifecycle hooks excluded** — `telemetry.py`, `session-posture`,
   `concise-reminder`, etc. are not in `GATE_HOOKS`; cross-tool telemetry of Codex runs is
   therefore absent.

## Why it is a problem
Items 1-3 mean the layer's advisory and turn-end value is claimed only as best-effort;
until verified, the "gates protect your work" story is only proven for hard `deny` blocks.
Item 4 adds per-tool-call latency in hours-long auto-mode (the user's primary workflow).
Item 5 leaves the hub blind to Codex gate/tool activity.

## Why it is not a duplicate
- [#74beb0fb](74beb0fb-opencode-stop-gate-emulation.md) — OpenCode stop-gate emulation
  (closed); this is Codex-native Stop-block behavior, a different runtime.
- [#e5308bd1](e5308bd1-opencode-telemetry-source-tag.md) — OpenCode telemetry source tag;
  this is whether to wire telemetry on Codex at all.

## What probably needs to be done
- Verify 1-3 in an isolated `CODEX_HOME` harness (see [[codex-adapter-passport]]:
  `CODEX_HOME=<throwaway>`, `codex exec … < /dev/null`, `--dangerously-bypass-hook-trust`).
  A hook emitting `additionalContext`/`systemMessage`; a hook emitting `"ask"`; a Stop hook
  emitting `{"decision":"block"}`. Record what actually reaches the model/user.
- If Codex supports tool-name matchers (confirm syntax), replace `.*` with per-tool
  matcher groups in `GATE_HOOKS`/`render_hooks_json` to cut spawns. **requires verification**
  of the Codex matcher semantics first.
- Decide whether to add `telemetry.py` (and which lifecycle hooks) to `GATE_HOOKS`;
  telemetry.py's session dimensions must be checked for Codex compatibility first.

## Acceptance criteria
- Items 1-3 have a recorded observed behavior (works / nudges / ignored), and the ADR
  0086 "best-effort" list is updated to "verified: <result>".
- If matchers are tightened: `test_build_codex.py` asserts per-tool grouping and a probe
  confirms a gate still fires; if not tightened, a note explains why.

## Sources
- `adapters/codex/build_codex.py` (`GATE_HOOKS`, `render_hooks_json`, `_hook_command`)
- `adapters/codex/gates/mainframe-hook.sh`
- `core/gates/detectors/path-validation.py` (`ask` verdict)
- `docs/decisions/0086-codex-adapter.md` — "Лог сборки Фазы 2", best-effort list

## Re-occurrence noted (2026-07-15)

The architecture audit quantified item 4: seven empty PostToolUse executions took 0.324 seconds, while a 5 MB hook payload took 1.739 seconds. The broad matcher launches every detector in the event group and `mainframe-hook.sh` launches an additional Python process to parse the payload. The ticket needs an explicit latency budget and a representative payload benchmark so an optimization cannot trade correctness for an unmeasured improvement.

The missing-detector degradation path discovered in the same audit has a separate root cause and is tracked in [#9a6f7945](9a6f7945-codex-missing-detector-silent.md).
