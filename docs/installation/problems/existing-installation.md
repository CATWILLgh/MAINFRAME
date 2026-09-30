# Existing MAINFRAME installation

## Use when

The target already contains MAINFRAME-named files, registrations, permissions,
or an older product-specific adapter.

## Desired result

One current effective component per inventory identity, with user-owned and
native state preserved and obsolete owned residue removed only after replacement
proof.

## Inspect

Search only the target product's already resolved configuration roots. Compare
stable names, registrations, source markers, paths, and semantic bodies. Classify
ownership as current MAINFRAME, obsolete MAINFRAME, unrelated, or unknown.

## Adapt

Update a current owned identity in place. Install the replacement beside an
obsolete identity only when required for safe verification, then remove the old
one. Preserve unknown ownership.

For hooks, replacement proof does not establish that an older session forgot
the previous callback. Follow the
[hook retirement sequence](rollback-and-recovery.md#retire-hooks-safely)
before moving or deleting its executable, dependencies, or state.

When the current inventory removes an old identity, first inspect its existing
state and owned target references. Remove only positively identified obsolete
MAINFRAME content and registrations after proving current components no longer
depend on them. Remove the old state row after cleanup; if ownership or
dependencies remain ambiguous, keep the recovery pending and report the exact
blocker instead of losing the only record of the obsolete identity.

If a maintained global instruction receipt exists but its ownership markers no
longer do, stop before appending another copy. First compare the effective file,
the current canonical instruction, and the preserved receipt. When the entire
effective file is exactly the current canonical body and the user has authorized
that body as the sole global instruction, wrap that same body in the maintained
boundary and reconcile the receipt atomically. This changes ownership without
changing instruction semantics. Preserve or explicitly reconcile any other
content; never restore an archival copy as current user intent merely because
its hash matches an older receipt.

## Verify

Reload the product, prove one effective identity and behavior, and check for
duplicate discovery, events, commands, permission rows, or skill descriptions.
Reconcile the same current inputs a second time and confirm equivalent content
and registrations without another write. Recheck after removing a predecessor
so proof does not depend on the obsolete copy.

## Record

Keep delivery and verification separate under
[verification.md](../verification.md). Put an unfinished cleanup or proof step
in `next_action`; reserve `reason` for an actual product limitation.
Report what obsolete owned material was removed.

## Never do

Never broadly scan the home directory, restore an archive as current truth, or
delete a same-named item without positive MAINFRAME ownership evidence.
