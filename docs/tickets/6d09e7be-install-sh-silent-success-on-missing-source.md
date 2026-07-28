---
id: 6d09e7be
title: install.sh reports success after missing sources or requested adapters
status: approved
priority: high
component: install
discovered: 2026-07-13
discovered-from: []
tags: ["install", "delivery", "silent-failure", "robustness"]
---

# 6d09e7be: install.sh reports success after missing sources or requested adapters

## What was observed
`install_one` checks the source before linking: on a missing source it prints
`log_warn "skipping: source ${src_rel} does not exist in repo"`
(`install.sh:263-264`) and returns non-zero — but the callers in the main
install path do NOT check the return code, so the overall run continues and
`install.sh` exits 0. The pre-existing `~/.claude/skills/mainframe` (and other)
symlinks are left pointing at the now-missing source, i.e. dangling. Same
warn-but-continue shape in `_bootstrap_secrets` (`:378-379` secret helper,
`:429-430` index template) and the OpenCode block.

The same root condition affects explicit adapter requests. When `--opencode` or `--codex` is supplied, a missing product binary or `.venv` returns success from the adapter function. Generator failures are caught by the main flow, which continues and unconditionally prints `Install complete`. A temporary-home probe with both binaries absent reproduced two adapter-skip warnings followed by exit status zero.

## Why it is a problem
A typo or a stale path in the `ARTIFACTS` / `MANAGED_DIRS` / adapter arrays
silently ships a BROKEN install: the command reports success (exit 0), the
symlink dangles, and the `mainframe` plugin is dead in every project until the
next manual re-run. The failure surfaces far from its cause (a later session
notices missing hooks/agents), not at install time. For a delivery-critical
script this violates the fail-fast principle — a delivery error must be loud and
exit non-zero, not a warning line buried in otherwise-green output.

For an explicit adapter flag, the equivalent failure is a wholly absent or stale adapter despite an apparently successful rollout.

## Why it is not a duplicate
Searched `docs/tickets/` for `install.sh` / silent / exit-code / `install_one`
/ skipping — no existing ticket covers install-time source-existence hardening.
The matches found are OpenCode / telemetry / unrelated.

## What probably needs to be done
- Distinguish REQUIRED sources (core `ARTIFACTS`, plugin, and every explicitly
  requested adapter) from legitimately OPTIONAL / mode-conditional ones. A blanket "fatal on any
  missing" would wrongly abort valid partial installs — this is why the fix is
  its own change, not a rider.
- For REQUIRED sources: make a missing source FATAL (collect all, print each,
  exit non-zero) so the run fails loudly instead of dangling a symlink.
- Consider a final post-install verification pass: enumerate every symlink the
  run created and assert each resolves (`readlink -f` non-dangling), exit
  non-zero on any dangle. This also catches paths the per-source check misses.
- requires verification: audit which array entries are truly required vs
  optional before choosing per-entry fatality.

## Acceptance criteria
- A missing REQUIRED source causes `install.sh` (and `--dry-run`) to exit
  non-zero with a clear message naming the missing path(s).
- Optional / mode-conditional sources still skip gracefully without aborting.
- `--opencode` and `--codex` exit nonzero when their executable, `.venv`, or generator is unavailable.
- The installer prints an unqualified completion message only when every explicitly requested target succeeded.
- A regression test (or a `--dry-run`-based assertion) proving a seeded missing
  required source is detected and returns non-zero.

## Sources
- `install.sh:258-286` (`install_one` warn-and-return, callers ignore the code)
- `install.sh:378-379`, `install.sh:429-430` (`_bootstrap_secrets` same shape)
- `install.sh:639-646`, `install.sh:793-800` (requested adapters return success after prerequisite skips)
- `install.sh:1073-1087`, `install.sh:1104-1105` (adapter failures are caught before unconditional completion)
- Temporary-home missing-binary reproduction, 2026-07-15
- Surfaced during the `dist/<tool>/` render-dirs consolidation
  (advisor #1, 2026-07-13): the consolidation's verify gate works around this by
  grepping `--dry-run` output for `skipping:` across all modes, but the
  underlying silent-success behavior remains and should be fixed on its own.

## Re-occurrence noted (2026-07-15)

**Noticed during:** Repair and independent edge review of Codex permission decisions (`#95878fc4`)
**Where:** `install.sh`, explicit `--codex` path
**Additional details:** Generator and native-validation failures now propagate to the top-level exit status, but an absent `codex` binary or repository `.venv` still returns success and remains owned by this ticket.

## Resolution (2026-07-15)

**Implementer:** Codex
**Commits:** `16b84941fbfc0ea480824d7f659a20257deca989`
**Summary:** The installer now validates required authored sources before its first installation mutation, treats missing prerequisites or failed generators for explicitly requested adapters as final failures, and preserves documented optional layers. The isolated contract suite also fixed destructive dry-run uninstall behavior and recovery of dangling managed links.
**Claims to verify on audit:**
- Missing required files or non-empty directories produce a nonzero dry-run result naming every missing source, without printing `Install complete`.
- Missing OpenCode/Codex executables, repository `.venv`, or generator success produce a final nonzero result while optional bootstrap phases still execute.
- `--uninstall --dry-run` bypasses install preflight, reports both normal and dangling managed links, and does not remove them.
- Codex installation still passes `--validate-native`; optional rules and generated dev runtime remain optional.
- `tools/test_install.py` passes 13/13, all 29 Python test files pass, and base/Codex/OpenCode dry runs complete successfully without a non-dry delivery command.
- Commit `16b8494` excludes user-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` changes.

## Audit (2026-07-15)

**Auditor:** Codex independent review agent
**Verdict:** Approved
**Verified:**
- Missing required sources — confirmed with the isolated contract suite and an additional two-source probe: both missing paths were reported, the dry run returned nonzero, omitted `Install complete`, and created no home-directory state.
- Requested adapter failures — confirmed for absent OpenCode/Codex executables, absent repository `.venv`, and failed generators; each produced a final nonzero result while later optional bootstrap phases remained observable. Successful generators preserved a zero result and `Install complete`.
- Uninstall safety — confirmed by the isolated dangling-link fixture and a real `--uninstall --dry-run`: install preflight was bypassed, normal and dangling managed links were reported, no link was removed, and repository status remained unchanged.
- Projection contracts — confirmed that Codex still receives `--validate-native`; absent optional rules and the generated development runtime do not fail installation, while hidden-only item directories fail preflight.
- Verification counts — `tools/test_install.py` passed 13/13; all 29 `tools/test_*.py` files passed; base, Codex, and OpenCode dry runs each exited zero with `Install complete`; `bash -n install.sh` and the commit-scoped `git diff --check` passed.
- Commit scope — `16b84941fbfc0ea480824d7f659a20257deca989` changes only `.github/workflows/ci.yml`, `install.sh`, `tools/test_install.py`, and the replaced `tools/test_install_codex.py`; it excludes user-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` state.
**Regression scan:** All 29 Python test files passed. The committed source contains no new suppression markers or debug residue, the generalized test keeps the prior Codex native-validation wiring assertion, and its standard-library-only dependencies are compatible with the early CI test phase.
**Notes:** Every direct installer invocation during this audit included `--dry-run`; no delivery command ran and the before/after repository status was identical. The Resolution wording “generator success” was interpreted as absence of generator success (generator failure), consistent with the Summary, acceptance criteria, and paired success/failure tests.
