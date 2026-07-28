# Delivery foundation readiness

This document defines when MAINFRAME's delivery foundation is complete. It is
the focused completion checklist for the architecture in
[installer-strategy.md](installer-strategy.md); that document remains the
normative source for runtime isolation, ownership, planning, and execution.

The goal is not to add more skills, agents, adapters, or MCP servers. The goal
is to make the existing product installable, changeable, removable, repairable,
and updatable without a repository checkout and without hidden cross-adapter
dependencies.

## Completion rule

The delivery foundation is complete only when all gates below are closed.
Passing a later gate does not compensate for an earlier one.

| Gate | Required outcome | Current state |
|---|---|---|
| 1. Empty-home install | A packaged `mainframe` can plan and install into an actually empty temporary home | Blocked by unsupported generic resources |
| 2. Reversible lifecycle | Install, no-op, change, remove, and reinstall preserve user-owned data | Partial; links and several adapter projections are reversible, generic resources are not |
| 3. Safe credentials | Secrets are resolved by name only where needed and never exported wholesale | Blocked by the compatibility shell bootstrap |
| 4. Adapter isolation | Each adapter works without another adapter's runtime files or directories | Modeled and broadly tested; full lifecycle parity remains |
| 5. CLI and TUI parity | A human or agent can inspect, prepare, preview, confirm, apply, and explain the same operation | Partial; narrow confirmed Context7 Apply exists |
| 6. Fault safety | Conflicts, interruption, concurrency, malformed state, and rollback fail without data loss | Implemented for the executor core; incomplete for every resource lifecycle |
| 7. Local release lifecycle | A verified immutable release can be imported, activated, switched, and rolled back | Import and exact-path loading exist; command wiring and activation are missing |
| 8. Standalone bootstrap | A new machine can install without cloning the repository or already having MAINFRAME | Missing |
| 9. Platform artifacts | Supported Darwin/Linux and architecture artifacts are built and exercised | Partial CI coverage; no published artifact matrix |
| 10. Trusted network update | Update metadata authenticates the publisher and downloads only the selected closure | Deferred until local lifecycle is complete |

## Required order

### 1. Make first installation honest

- Test the real packaged binary against an empty temporary home.
- Do not pre-create target roots that a new user would not have.
- Bind every installed source to the already validated release snapshot.
- Install no shell startup line that exports the complete credential store.
- Keep general Apply disabled until every planned write has safe ownership and
  removal semantics.

### 2. Complete reversible ownership

- Record whether MAINFRAME created a file, owns an exact entry, or merely
  observed user state.
- Remove only exact, registry-proven MAINFRAME state.
- Preserve changed, foreign, malformed, and user-owned state.
- Prove install, repeated no-op, reconfiguration, removal, and reinstall.
- Prove rollback and recovery at every persisted transaction boundary.

### 3. Close adapter lifecycle parity

- Exercise OpenCode and Antigravity 2.x first because their live environments
  are not the user's active daily sessions.
- Exercise Claude Code and Codex last and only after explicit preparation.
- Verify each adapter with every other adapter root absent.
- Verify selecting or removing one adapter cannot mutate a sibling adapter.

### 4. Complete local release delivery

- Connect the immutable release store to a user-facing import command.
- Activate `$HOME/.local/bin/mainframe` against one exact imported release.
- Switch versions atomically and retain an understandable rollback target.
- Make TUI and CLI use the same release identity, reviewed plan, confirmation,
  transaction, and result.

### 5. Add standalone bootstrap and platform packages

- Produce named artifacts for each supported operating system and
  architecture.
- Verify archives and checksums before local import.
- Install the first `mainframe` command without a repository checkout, Python
  project environment, or existing MAINFRAME installation.
- Keep `install.sh` as the compatibility path until this route has observable
  lifecycle parity.

### 6. Add network updating last

- Authenticate the publisher rather than trusting hashes alone.
- Define trusted update metadata, rollback protection, and key rotation.
- Download only the selected adapters and their explicit neutral dependencies.
- Preserve an installed known-good release when an update fails.

## Verification matrix

Every lifecycle-capable component must pass:

- fresh install in an empty temporary home;
- repeated application with no changes;
- add, replace, deselect, remove, and reinstall;
- user-modified and foreign-file preservation;
- symbolic-link and malformed-state rejection;
- concurrent mutation rejection;
- interruption, rollback, and repeated recovery;
- restrictive file and directory modes;
- execution on native Darwin and native Linux;
- absence of unselected adapter roots and changes.

Tests use temporary roots and packaged releases by default. Live Claude Code
and Codex configurations are outside automated verification and require a
separate, explicit smoke-test window.

## Release boundary

A local development milestone may close gates 1–7 without network delivery.
A public standalone release requires gates 1–9. Automatic or remote updating
requires all ten gates.

Until the relevant boundary is met:

- the TUI must describe unavailable actions plainly;
- narrow Apply paths must not be presented as complete installer support;
- `install.sh` remains the documented compatibility installer;
- release hashes must not be described as publisher authentication.

## Tracked work

- General safe Apply: [#7a1c1d1d](tickets/7a1c1d1d-add-safe-plan-application.md)
- Configuration lifecycle: [#cd5f584d](tickets/cd5f584d-complete-configuration-lifecycle-semantics.md)
- Release publisher authentication: [#d3b15da9](tickets/d3b15da9-authenticate-release-publisher.md)
- Selective downloads: [#33930a3b](tickets/33930a3b-enable-selective-release-downloads.md)
- Long-plan navigation: [#1d04acea](tickets/1d04acea-add-tui-plan-scrolling.md)
- Strategy document split: [#3a79360e](tickets/3a79360e-split-installer-strategy-by-concern.md)

The shell-wide secret export is a known local finding. It must be replaced as
part of gate 3 before the new installer can own shell integration.
