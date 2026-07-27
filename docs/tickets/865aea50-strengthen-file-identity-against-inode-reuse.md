---
id: 865aea50
title: Strengthen file identity against same-inode replacement
status: open
priority: medium
component: installer
discovered: 2026-07-19
discovered-from: []
tags: ["filesystem", "identity", "linux", "recovery", "security"]
---

# 865aea50: Strengthen file identity against same-inode replacement

## What was observed

The link workspace records file identity as device and inode. During the first
Ubuntu CI run, Linux immediately reused the inode after a symbolic link was
removed and recreated with the same target. The recreated link therefore
matched the saved identity even though it was a different filesystem object.

The failing test intended to exercise a different-inode replacement, so its
setup was corrected by keeping both inode allocations alive. The broader
same-inode replacement remains outside that test contract.

## Why it is a problem

An external process that replaces a managed entry between inspection and
publication could theoretically receive the same inode. If its other observable
properties also match, MAINFRAME may treat the replacement as the inspected
object and mutate ownership it no longer controls.

## Why it is not a duplicate

No existing ticket covers inode reuse or strengthening `FileIdentity`. The safe
plan application ticket tracks transaction recovery and exact ownership at the
current identity contract; this ticket questions whether that contract is
strong enough against an ABA-style replacement.

## What probably needs to be done

- Evaluate platform-stable identity signals beyond device and inode, including
  change time, birth time, or descriptor-backed handles.
- Define migration and compatibility rules for persisted transaction journals.
- Apply the stronger identity consistently to links, configuration files,
  directories, pinned roots, recovery validation, and legacy-journal upgrade.
- Add a Linux fixture that deliberately obtains same-inode reuse and proves the
  replacement is rejected.

## Acceptance criteria

- [x] Persisted identity no longer compares an entry by device and inode alone.
- [ ] A recreated entry remains distinguishable when Linux reuses an inode
  inside one birth-timestamp resolution quantum.
- [x] Existing journals either migrate safely or fail closed with an actionable
  compatibility error.
- [ ] Darwin and Linux tests cover link, configuration, directory, and recovery
  identity checks.
- [x] No identity metadata permits traversal through symbolic-link ancestors.

## Progress (2026-07-26)

- Persisted file identity now combines device, inode, and birth timestamp for
  links, configuration files, managed directories, pinned roots, prepared read
  preconditions, and transaction recovery. This is a stronger fingerprint, not
  a filesystem generation number: coarse birth-timestamp resolution leaves a
  residual same-inode collision risk, so the absolute ABA criterion remains open.
- Darwin reads the birth timestamp from `stat`. Linux requires `statx` with a
  returned `STATX_BTIME` bit and fails closed when the filesystem cannot supply
  it. Darwin mutation support remains limited to local APFS and HFS filesystems,
  which provide native creation timestamps. Identity inspection remains
  descriptor-relative and does not follow a symbolic-link leaf.
- Journal schema version 4 persists the complete identity. Empty older journals
  can upgrade, while identity-bearing version 2 or 3 journals fail closed with
  recovery guidance because their missing birth timestamp cannot be recreated
  safely.
- Real Darwin tests cover stable directory and renamed-link identities plus
  recreated entries. Linux-specific tests cover a missing `STATX_BTIME` result
  and a changed birth timestamp with the same device and inode. The complete
  Linux suite still needs to execute natively in CI; cross-compilation alone
  does not satisfy the remaining acceptance item.
- Public CLI JSON continues to omit all internal identity fields.

## Sources

- `internal/executor/types.go:62`
- `internal/linkworkspace/filesystem_unix.go:183`
- `internal/linkworkspace/mutation_unix.go:317`
- `internal/linkworkspace/workspace_unix_test.go:194`
- Ubuntu CI run `29687225528`
- [Linux `inode(7)`](https://man7.org/linux/man-pages/man7/inode.7.html)
- [Linux `statx(2)`](https://man7.org/linux/man-pages/man2/statx.2.html)
- [Apple `stat(2)`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/stat.2.html)
