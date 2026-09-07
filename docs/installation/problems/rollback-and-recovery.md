# Rollback and recovery

## Use when

A target write fails, native verification regresses the existing environment, or
an interrupted run leaves temporary or duplicate MAINFRAME-owned state.

## Desired result

Restore only the affected pre-change target, preserve all unrelated state, and
leave adaptation status accurate and resumable.

## Inspect

Identify the exact component, files or registration changed by this operation,
its targeted rollback copy, current native effective state, and whether the new
component ever became active.

## Adapt

Stop further writes for the affected component. Restore the targeted prior file
or registration atomically where practical. If the new component is inactive
and independently removable, remove only its positively identified residue.

## Verify

Reload the product and prove the prior behavior or configuration is restored.
Check for duplicate registrations, broken symlinks, stale temporary files, and
orphaned test processes.

## Record

Return the component to `pending` with the exact blocker. Preserve completed
independent entries. Remove the rollback copy only after restoration proof.

## Never do

Never restore an entire profile archive, delete native caches or sessions,
rewrite the MAINFRAME worktree, or use broad destructive cleanup to recover one
component.
