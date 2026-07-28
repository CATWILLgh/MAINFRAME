---
id: 057688a7
title: mainframe-gates.js exceeds 400 lines and its event handler is cyclomatically complex
status: open
priority: low
component: opencode-plugin
discovered: 2026-07-13
discovered-from: []
tags: ["opencode", "refactor", "code-quality", "file-size"]
---

# 057688a7: mainframe-gates.js exceeds 400 lines and its event handler is cyclomatically complex

## What was observed

Adding the `session.idle` end-of-turn stop-gate emulation (ticket 74beb0fb)
grew `adapters/opencode/plugins/mainframe-gates.js` to 411 lines (hub rule:
< 400) and the `event` handler to 57 lines / cyclomatic 19 (fallow flags it
"critically complex"). Both are advisory notes from the hub's own length + fallow
gates, surfaced on the change that introduced them.

## Why it is a problem

The hub's engineering rules cap files at 400 lines and functions at 60 lines,
and treat high cyclomatic complexity as a maintainability smell. The `event`
handler folds several concerns (git precheck, two gate scans, toast dedup,
nudge loop-guard, security-clean reset) into one function — readable now, but a
refactor target.

## Why it is not a duplicate

Distinct from [#6badea13](6badea13-fallow-recon-js-fp-and-complexity.md) (that
covers skill `recon.js` FPs + their complexity). This is the OpenCode plugin
file itself.

## What probably needs to be done

- Extract the idle stop-gate logic (constants + `runStopGate`/`scanGates` +
  the `event` handler body) into a co-located module imported by
  `mainframe-gates.js`. IMPORTANT deployment nuance: OpenCode's legacy plugin
  loader iterates the PLUGIN module's exports and throws on any non-function
  export — but it does NOT scan imported modules, so a helper module is safe
  to import. The deployed plugin is a SYMLINK into `adapters/opencode/plugins/`;
  a relative `./idle-gate.js` import resolves against the symlink target, so the
  helper must be co-located there and covered by whatever deploys the plugin
  (verify `install.sh --opencode` / the symlink strategy ships both files).
- Decompose the `event` handler into named steps (scan → toast → nudge) to drop
  the cyclomatic count.
- Keep the 40 `test_mainframe_gates.mjs` tests green across the refactor (they
  pin the observable contract, so a pure restructure stays covered).

## Acceptance criteria

- `mainframe-gates.js` (or its split parts) each under 400 lines; the idle
  handler decomposed so no single function is critically complex.
- The plugin still loads in OpenCode (banner + a live idle nudge), and all 40
  node tests pass.

## Sources

- length-quality-note + fallow note, 2026-07-13 (this session).
- `adapters/opencode/plugins/mainframe-gates.js` — the `event` handler.
- Plugin-loader export constraint: anomalyco/opencode v1.17.18
  `packages/opencode/src/plugin/index.ts` `getLegacyPlugins`.

## Re-occurrence noted (2026-07-15)

The audit re-measured `adapters/opencode/plugins/mainframe-gates.js` at 401 lines, so the file remains above the repository limit. This ticket continues to own that adapter-specific split; the other infrastructure size findings are tracked separately to keep implementation units atomic.
