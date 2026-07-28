---
id: 67388f9b
title: OpenCode gates scan the session root, not the actual command cwd — a cd'd commit evades the secret gate
status: closed
priority: low
component: opencode-plugin
discovered: 2026-07-13
discovered-from: []
tags: ["opencode", "security", "gate", "cwd", "limitation"]
---

# 67388f9b: OpenCode gates scan the session root, not the actual command cwd — a cd'd commit evades the secret gate

## What was observed

Desktop-app probe (2026-07-13): a `git commit` staging a fake AWS key ran in a
side folder (`/tmp/.../gate-probe`) while the app's open project (session root)
was a different repo. The secret-commit gate did NOT block; the
commit-convention advisory (pure command-string parse) DID fire. Root-caused
via source: the plugin factory receives `input.directory = ctx.directory` (the
fixed session/project root), and the `tool.execute.before` trigger passes only
`{ tool, sessionID, callID }` + `{ args: { command } }` — NO per-command cwd
(anomalyco/opencode v1.17.18 `plugin/index.ts:153`, `session/tools.ts:106`).
`mainframe-gates.js` therefore runs `secret-commit-gate.py` with
`cwd = session root`, so `git diff --cached` scans the wrong repo and
fail-opens. A control run with the session root SET to the bait repo
(`opencode run --dir <bait>`) blocks correctly.

## Why it is a problem

The normal threat model IS covered: committing a secret into your open project
means session root = commit repo → the gate scans it → blocks (verified). But
a commit whose effective cwd differs from the session root — `cd sub && git
commit`, a nested git repo under the project, or a monorepo subdir — is not
scanned. Low real-world severity (the common path works), but it is a genuine
coverage hole a determined evasion or an unusual layout can hit.

## Why it is not a duplicate

No existing ticket covers the OpenCode gate cwd binding. Distinct from the
runtime-portability fix (`bcb3cfb`), which addressed the plugin loading at all
in the desktop app.

## What probably needs to be done

- Requires verification: whether OpenCode's before-hook can be given the
  effective command cwd (feature request upstream), OR whether parsing a
  leading `cd <path> &&` out of the bash command to reset the gate cwd is
  worth the fragility (rejected forms: subshells, `pushd`, `git -C`).
- Interim: document the limitation in the OpenCode adapter notes so it is not
  mistaken for a working guarantee; keep the CC hook (which receives the real
  cwd) as the stronger enforcement surface.
- Decide whether the residual gap justifies any change at all, or is an
  accepted platform limitation recorded here.

## Acceptance criteria

- Decision recorded (fix / accept-as-limitation) with the source backing it.
- If accepted: the adapter's runtime notes state that gates bind to the
  session root, so commits outside the open project are not scanned.

## Sources

- Live probe + CLI reproduction, 2026-07-13.
- anomalyco/opencode v1.17.18 `packages/opencode/src/plugin/index.ts:153`
  (`directory: ctx.directory`), `packages/opencode/src/session/tools.ts:106`
  (before-trigger payload has no cwd).
- `~/.claude/skills/mainframe/hooks/scripts/secret-commit-gate.py:71,150`
  (`git rev-parse` / `git diff --cached` run in the gate's cwd).

## Resolution (2026-07-13)

**Implementer:** engineering session (task-workflow).
**Commits:** 8693104.
**Summary:** Fixed in the existing gate plugin (no new plugin — recon showed
the cwd case needs no state). `effectiveCwd(command, workdir, projectRoot)`
computes where a bash command actually runs: the `workdir` param resolved
against root (OpenCode's own recommended alternative to `cd`), then leading
`cd`/`pushd` segments; subshell / command-substitution bails to the start.
Wired so the bash payload `cwd` = effective while `project_dir` stays root.
A computed cwd that does not exist falls back to root (guards the wrong-repo
miss a `cd $VAR` literal-parse could cause — never worse than pre-fix).
Recon corrected the scope: `cd` into a subdir of the SAME repo was already
caught (git index is repo-wide); the real gaps closed are `workdir` and
nested separate repos.

**Claims to verify on audit:**
- `.venv`-free `node tools/test_mainframe_gates.mjs` → 28 pass, incl. 6
  effectiveCwd unit tests, the spawn-cwd wiring test, and the non-existent
  fallback test.
- Deterministic gate check: the same staged fake key in a nested separate
  repo returns `deny` when the gate runs with cwd=nested and passes (no
  block) with cwd=root — the exact before/after the fix changes.
- `project_dir` remains the project root in the bash payload (path-validation
  boundary unchanged).

## Audit note

Independent `decision-reviewer` pass on the diff pre-commit returned
proceed-with-mitigations; its one Medium finding (non-existent computed cwd →
wrong-repo miss) was fixed inline (the existsSync→root fallback) with a
regression test before commit.
