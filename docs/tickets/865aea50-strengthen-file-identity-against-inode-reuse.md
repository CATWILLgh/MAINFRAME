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

- A recreated entry cannot compare equal to the inspected entry solely because
  Linux reused its inode.
- Existing journals either migrate safely or fail closed with an actionable
  compatibility error.
- Darwin and Linux tests cover link, configuration, directory, and recovery
  identity checks.
- No identity metadata permits traversal through symbolic-link ancestors.

## Sources

- `internal/executor/types.go:62`
- `internal/linkworkspace/filesystem_unix.go:183`
- `internal/linkworkspace/mutation_unix.go:317`
- `internal/linkworkspace/workspace_unix_test.go:194`
- Ubuntu CI run `29687225528`
