# Rollback and recovery

## Use when

A target write fails, native verification regresses the existing environment,
an interrupted run leaves temporary or duplicate MAINFRAME-owned state, an
authorized disable or removal retires a hook, or final cleanup must remove
residue from this installation's probes.

## Desired result

Restore only the affected pre-change target, preserve all unrelated state, and
leave adaptation delivery and verification accurate and resumable.

## Inspect

Identify the exact component, files or registration changed by this operation,
its targeted rollback copy, current native effective state, and whether the new
component ever became active. For probes, identify the exact temporary paths,
processes, trust or permission rows, and hook state created by this operation.
Keep this bounded working list as probes run; do not search an entire profile
afterward or inspect protected stores to reconstruct it.
Record native probe scope IDs and the exact state keys derived from them before
cleanup. Matching a file count, owner, age, or empty contents does not establish
that a concurrent session's file belongs to this operation.

## Adapt

Stop further writes for the affected component. For hooks, follow the retirement
sequence below before removing or moving any callable file. Otherwise restore
the targeted prior file or registration atomically where practical. If the new
component is inactive and independently removable, remove only its positively
identified residue.

After each probe, retire its hooks safely, stop its processes, and remove only
its temporary files, registrations, trust entries, bytecode, and hook state. Remove temporary
permissions from the exact owner where the probe added them, preserving user
entries and concurrent changes. Remove an empty directory only when this
operation created it. Native caches and real sessions remain preserved.

### Retire hooks safely

Removing a registration from disk does not prove running sessions forgot it.
Moving its executable into a rollback directory also breaks the old path.

The [maintained Codex route](../codex-installer.md#disable-enable-remove-recover)
keeps its guarded entrypoint in the cached inline command and system shell.
That retained entrypoint stays neutral when the implementation is absent;
implementation removal does not require deleting a cached callable path.
Do not apply this exception to older registrations that name a removable file.

1. Identify the exact owned registrations, callable paths, dependencies, and
   affected running scopes. Preserve shared files still used by other hooks.
2. Disable the owned hook through its verified native control. If running scopes
   retain the callback, use the adapter's explicit disabled path while keeping
   its entrypoint and launch runtime reachable. Confirm late callbacks are
   neutral before removing detector bodies or state. Do not remove dependencies
   until in-flight invocations finish.
3. Remove or restore only the owned registrations. Preserve unrelated entries
   and concurrent edits. For replacement or rollback, prepare the target before
   switching registration and prove its intended behavior.
4. Reload the affected product scopes through the supported mechanism and prove
   obsolete callbacks no longer run. A fresh session alone does not prove an
   older session unloaded them. Preserve real sessions and their work; when a
   user-operated restart is required, return that exact remaining step.
5. Remove the obsolete entrypoint and its unused dependencies last, then clean
   owned state and verify effective registrations. Until unloading is proven,
   retain the minimal inert entrypoint, record its exact path and reload blocker
   in `next_action`, and keep delivery pending.

If a missing launcher already blocks every tool or repeatedly continues a turn,
do not retry the same commands or resubmit the same completion explanation.
Report the broken path and required native disable or reload once. If repair is
denied, stop that action rather than changing tools to bypass the denial.

## Verify

Reload the product and prove the prior behavior or configuration is restored.
Check for duplicate registrations, broken symlinks, stale temporary files, and
orphaned test processes. Confirm removed probe registrations and trust rows no
longer appear in the effective configuration; deleting only their fixture
directory is insufficient.

## Record

Return component delivery to `pending` with the exact recovery step in
`next_action`. Preserve completed independent entries. Remove the rollback copy
only after replacement or restoration proof. If recovery remains pending, retain
the protected copy and the one non-secret recovery pointer needed to resume; do
not claim cleanup complete until recovery is resolved.

## Never do

Never restore an entire profile archive, delete native caches or sessions,
rewrite the MAINFRAME worktree, or use broad destructive cleanup to recover one
component.
