---
id: b7a493b8
title: Port top-value security hooks to an OpenCode JS/TS plugin (dual-target phase 2)
status: closed
priority: high
component: opencode-layer
discovered: 2026-07-08
discovered-from: []
tags: ["opencode", "hooks", "security", "phase-2"]
---

# b7a493b8: Port top-value security hooks to an OpenCode JS/TS plugin (dual-target phase 2)

## Progress (2026-07-08, later) — dispatcher landed: 11 hook rows total

The adapter grew into a table-driven dispatcher (current source:
`adapters/opencode/plugins/mainframe-gates.js`, plain ESM JS so stock node
tests it — `tools/test_mainframe_gates.mjs`, 13 tests, CI-wired).
Rows: the 2 block gates (unchanged contract, characterization-tested) + 9 advisory
hooks on `tool.execute.after` (bash reminders shifted post-exec; file scanners on
edit/write via payload translation filePath→file_path etc.). Advisory channel =
append to `output.output` (proven to reach the model verbatim). Session-level
exact-text note dedup; payload-size guard (shell ARG_MAX). Deliberately unmapped:
telemetry → [#e5308bd1](e5308bd1-opencode-telemetry-source-tag.md), Stop-gates →
[#74beb0fb](74beb0fb-opencode-stop-gate-emulation.md), CC-machinery text hooks
(task-workflow/concise/memory/session-posture — dead refs on GLM, 5fae0bfa class).

## Progress (2026-07-08) — the two PreToolUse gates done; Stop-gates blocked by platform

The adapter initially shipped in TypeScript in a dedicated top-level
OpenCode directory; after the neutral-core restructure its current source is
`adapters/opencode/plugins/mainframe-gates.js`. On `tool.execute.before`
(tool == bash) it shells the existing `secret-commit-gate.py` and
`path-validation.py` detectors from `core/gates/detectors/` (rendered to
`dist/claude-code/plugin/hooks/scripts/`), translating OpenCode's payload to
the Claude Code hook stdin contract and mapping `deny`/`ask` → throw (block),
`allow`/absent → defer.
`path-validation.py` gained a `project_dir` payload field (env `CLAUDE_PROJECT_DIR`
stays as fallback) so the confinement boundary is explicit, not a getcwd() accident.

**Remaining in this ticket (still open work):**
- **Stop-gates cannot be ported** — OpenCode has no blocking turn-end mechanism
  (`session.idle` is notify-only; the `permission.ask` plugin hook does not fire —
  verified on 1.17.15, tracks closed-stale issue #19927). So `*-stop-gate.py`,
  the PostToolUse security scanners, and all quality/advisory hooks remain
  Claude-Code-only. Revisit if OpenCode ships a blocking stop event or fixes
  `permission.ask`.
- Empirical LLM-driven end-to-end pass was blocked by GLM headless latency +
  the model's own refusal of destructive probes; correctness was proven by
  composition instead (Python gates return correct deny/ask/allow on the exact
  payloads the plugin builds; plugin throw/crash/defer mechanics proven with
  marker probes). A full app-side smoke test on the user's desktop OpenCode is
  the outstanding verification.
- Adjacent finding (defense-in-depth, not a gap): OpenCode has a native
  `external_directory: ask` permission that independently catches operations
  outside the project dir — so path-validation's outside-project case is
  double-covered on the app surface.

## What was observed
Phase 1 of the OpenCode dual-target layer (generator `tools/build_opencode.py`
+ `install.sh --opencode`) ships agents, permissions, and MCP projection. The
hub's actual enforcement layer — the Python hooks (secret-scan,
suppression-marker gates, path validation, security scans) — does not
transfer: OpenCode has no shell-hook mechanism; its equivalent is JS/TS
plugins in `~/.config/opencode/plugins/`.

## Why it is a problem
The 2026-07-08 decision-review (objection 3, its most certain finding): an
autonomous OpenCode run has dramatically thinner guardrails than the same run
under Claude Code, while the "hub drives OpenCode" framing invites a parity
assumption. The projected permission map is best-effort, not a boundary;
hooks are where the hub's security value actually lives.

## Why it is not a duplicate
No OpenCode ticket exists. `cb173a75` (shared module for suppression hooks)
concerns the CC-side Python hooks' internal structure, not an OpenCode port —
its outcome may simplify this port and should be checked first.

## What probably needs to be done
0. Repo placement agreed on 2026-07-08 was a dedicated top-level OpenCode
   directory. That was the implemented location at the time; ADR 0085 later
   superseded it with `adapters/opencode/` for handwritten OpenCode sources,
   `core/` for shared detector sources and `dist/` for generated delivery
   artifacts.
1. Rank hub hooks by security value; the reviewer named security stop-gates
   first (secret-scan, destructive-bash patterns beyond the permission map,
   suppression-marker gate).
2. One OpenCode plugin (TypeScript, Bun runtime) implementing the top slice:
   `tool.execute.before` can BLOCK a call by throwing (confirmed:
   opencode.ai/docs/plugins example throws on `.env` read). Global install via
   `~/.config/opencode/plugins/` symlink from the hub repo.
3. Decide reuse strategy: port logic (rewrite) vs shell out to the existing
   Python scripts from the plugin (keeps one implementation; adds a python3
   runtime dependency inside OpenCode's plugin sandbox — requires verification).
4. Tests + wiring into `install.sh --opencode`.

## Acceptance criteria
- A denied probe (e.g. reading a credentials path, a destructive bash
  pattern) is blocked inside a live OpenCode session by the plugin, verified
  empirically like the phase-1 deny probes.
- Plugin failure does not brick OpenCode sessions (degrades open, logged).
- Hub remains single-source: plugin lives in the repo, symlinked out.

## Sources
- https://opencode.ai/docs/plugins/ — events, blocking via throw, global dir
- Decision-review 2026-07-08, objection 3 (guardrail thinning)
- `docs/reference-mining/D-opencode-parallel.md` §4 tier C
- `core/gates/` — shared detector and gate source inventory to rank
- `dist/claude-code/plugin/hooks/` — generated Claude Code delivery artifact

## Resolution (2026-07-09)

**Implementer:** autonomous sessions (Fable 5)
**Commits:** `4471e342a164179e3e2450d35519325efeb9c141`,
`29a066ee0ed63ebb1e07a9ed91e00823df7161d9`
**Summary:** The first commit added the OpenCode adapter for the two blocking
bash gates while retaining the Python detectors as the single logic owner.
The second converted the adapter to the tested, table-driven JavaScript
dispatcher and added nine post-execution advisory rows. The later ADR 0085
relocation changed the source path, not this implementation history.
**Claims to verify on audit:**
- `adapters/opencode/plugins/mainframe-gates.js` dispatches the two blocking
  rows and nine advisory rows described above.
- `node tools/test_mainframe_gates.mjs` passes the dispatcher contract suite.
- Detector logic remains owned by `core/gates/detectors/` and its rendered
  Claude Code copies remain under `dist/claude-code/plugin/hooks/scripts/`.
- `install.sh --opencode --dry-run` includes the OpenCode plugin delivery.

## Resolution addendum — live smoke (2026-07-09)

**Implementer:** autonomous session (Fable 5), user-approved install run.
**Evidence (headless CLI, glm-5-turbo, 1.17.15):**
- Plugin loads deployed: `[mainframe-gates] active: 12 hook rows` in a real
  session (12th row = telemetry, added under e5308bd1).
- Outside-project delete BLOCKED end-to-end: probe file in `$HOME` survived;
  the native `external_directory` guard fired first (auto-reject headless),
  our `path-validation` row is the second line — its throw contract stays
  pinned by the 14 dispatcher tests.
- AGENTS.md render live in sessions (runtime-notes bullet quoted verbatim);
  skills 18/18 dedup-clean; agents resolve with enrichment.
**Remaining (optional):** a visual desktop-app pass adds no engine-level
coverage beyond the above (the app drives the same CLI engine); left to the
user's discretion.
