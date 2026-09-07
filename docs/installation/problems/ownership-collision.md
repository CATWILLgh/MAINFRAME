# Ownership collision

## Use when

A canonical identity or destination already exists but MAINFRAME ownership is
unclear, or existing user semantics conflict with the canonical component.

## Desired result

Preserve unrelated state and either reconcile a proven owned identity or obtain
one precise user decision about the semantic owner.

## Inspect

Read only the relevant file or registration metadata. Compare stable identity,
source markers, effective precedence, and semantic purpose. Distinguish a
formatting difference from a real behavior conflict.

## Adapt

Merge when both rules can coexist under the same established owner. Update in
place when ownership is proven. If choosing would remove or reverse user-owned
behavior, stop before writing and present the exact two outcomes.

## Verify

Prove the effective target contains one intended behavior and retains unrelated
content after reload.

## Record

Leave the component `pending` for an unresolved ownership decision. Do not use
`unsupported` for a decision that has not been made.

## Never do

Never append duplicate variants, weaken both rules into vague text, rename one
side to hide a collision, or overwrite unknown ownership.
