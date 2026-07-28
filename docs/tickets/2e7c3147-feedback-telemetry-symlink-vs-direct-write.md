---
id: 2e7c3147
title: Reconsider ~/.claude/mainframe symlink vs direct-write for telemetry/feedback data
status: open
priority: low
component: hooks
discovered: 2026-06-13
discovered-from: []
tags: ["telemetry", "feedback", "harness", "privacy", "install", "design"]
---

# 2e7c3147: Reconsider ~/.claude/mainframe symlink vs direct-write for telemetry/feedback data

## What was observed
The `--dev` instrumentation routes both data sinks through one symlink:
`~/.claude/mainframe` → `workspace/runtime/` (created in `install.sh:784-794`, mapped
in `DEV_ARTIFACTS` `install.sh:134`).

- Telemetry DB: `~/.claude/mainframe/telemetry/telemetry.db` (`_hooklib.py:230-235`).
- Feedback files: `~/.claude/mainframe/feedback/` (`feedback.py:57-59`).

The symlink serves double duty: (1) **locator** — a stable `~/.claude/`-anchored path a
hook running in any foreign project can write to without knowing the repo's clone
location; (2) **opt-in gate** — its presence = logging on, absence = off (off by default
on a plain install).

Two asymmetries surfaced while verifying the privacy guarantee:

1. **Telemetry self-gates, feedback does not.** `log_event` (`_hooklib.py:269-273`) only
   `makedirs` on the env-override path; on the default path it returns a no-op when the
   dir is absent — it can never create a stray directory. But `feedback.py:98` calls
   `os.makedirs(dir, exist_ok=True)` unconditionally. If the symlink is absent while the
   skill is still present (manual deletion of just the symlink), the next feedback write
   creates a **real** `~/.claude/mainframe/feedback/` directory **outside** the repo
   (not a symlink into `workspace/runtime/`, not gitignored).

2. **Direct-write is a viable alternative that was never compared.** The plugin scripts
   are symlinked into `~/.claude/skills/mainframe/`, so `os.path.realpath(__file__)`
   resolves into `<repo>/plugin-dist/...`; a hook could self-locate `<repo>/workspace/runtime/`
   (4 dirnames up) and write directly, dropping the symlink and its dangling-link /
   makedirs-outside-repo edge cases. The cost: `realpath` self-location only works under a
   *symlink* install — if the plugin is ever installed by **copy** (a real marketplace
   install), `realpath` lands inside the copy where `workspace/runtime/` does not exist,
   so direct-write breaks. The symlink decouples "where data goes" from "where the code
   lives" and survives a copy-install; that is its load-bearing advantage.

## Why it is a problem
Low severity, no impact in normal operation (install.sh creates skill + symlink together,
so "skill present ⟺ symlink present"; a dangling symlink makes `makedirs` fail loudly
rather than misplace data). The genuine leak path is narrow: delete only the symlink,
keep the skill, then feedback writes land outside the repo in a non-gitignored real dir.
The rationale for symlink-vs-direct is also undocumented (ADR 0073/0075 record neither),
so a future change could pick wrong without the tradeoff in front of it.

## Why it is not a duplicate

- [#8f2571e3](8f2571e3-runtime-telemetry-and-session-state-have-no-retention-policy.md)
  owns age/size limits and cleanup after runtime data exists. This ticket owns
  the locator and opt-in mechanism, plus the orphan feedback-write path when
  the legacy Claude Code symlink is absent.
- [#fb0f169b](fb0f169b-apply-adapter-local-diagnostics.md) owns the newer
  cross-adapter activation, storage, and lifecycle contract. It does not
  resolve whether the legacy `--dev` Claude Code sink should retain its
  symlink or self-locate, nor the `feedback.py` asymmetry recorded here.
- [#5a1d3094](5a1d3094-serve-local-diagnostics-dashboard.md) owns read-only
  presentation of diagnostics. It does not own where writers place data.
- [#d38d93a4](d38d93a4-add-antigravity-hook-diagnostics.md) owns bounded,
  redacted Antigravity failure records, a different adapter and data class.

## What probably needs to be done
Decision, not a forced change. Two coherent options:

- **Keep the symlink, harden `feedback.py`** to match telemetry's discipline: resolve
  `realpath` of the target and refuse to write if it is not inside `workspace/runtime/`,
  OR require the dir to pre-exist instead of `makedirs`-ing it. Closes asymmetry #1, keeps
  distribution-independence. ~10 min + a test in `test_feedback.py`.
- **Switch both to direct-write via `realpath(__file__)`** + an explicit gate dir
  (`<repo>/workspace/runtime/<sink>/` existence). Removes the symlink and its whole edge-
  case class, but couples data to the code's physical location and assumes symlink-install
  forever (breaks under copy-install).

Recommendation (current): first option — the symlink is the more distribution-robust
model; its only real downside is the `feedback.py` asymmetry, which is a small fix.

## Acceptance criteria
- A recorded decision (this ticket → resolution, or a short ADR note) stating which model
  the hub keeps and why.
- If "harden `feedback.py`" is chosen: feedback writes outside `workspace/runtime/` are
  refused (or impossible), covered by a Tier-1 test; no behaviour change in the normal
  `--dev` path.

## Sources
- `plugin-dist/hooks/scripts/_hooklib.py:230-289` (telemetry path + gated no-op).
- `dev/skills/harness-feedback/feedback.py:57-98` (feedback path + unconditional makedirs).
- `install.sh:128-134`, `install.sh:784-794` (DEV_ARTIFACTS + --dev-only creation).
- ADR 0073 (telemetry), ADR 0075 (harness-feedback) — neither records the symlink-vs-direct choice.
