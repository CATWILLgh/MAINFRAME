---
id: 924bb513
title: Define power-loss durability for direct bundle publication
status: open
priority: low
component: bundles
discovered: 2026-07-19
discovered-from: ["#66ab4af8"]
tags: ["darwin", "durability", "fsync", "publication", "recovery"]
---

# 924bb513: Define power-loss durability for direct bundle publication

## What was observed

Direct adapter bundles now publish through a journaled native directory swap
and recover after a publisher process stops at any protocol boundary. The
immediately previous generation is retained until the next successful
publication, which avoids deleting it during the commit that displaced it. The
contract deliberately does not claim that macOS has durably ordered every
directory entry when the machine loses power or the operating system crashes.
Apple documents ordinary `fsync` as weaker than a full hardware flush.

## Why it is a problem

OpenCode and Codex development installations can consume the direct generated
trees through persistent links. A power loss after the namespace swap but near
old-generation cleanup could require a rebuild and may not preserve the same
old-or-new recovery guarantee proven for an ordinary process interruption.

## Why it is not a duplicate

- [#66ab4af8](66ab4af8-make-bundle-publication-atomic.md) closes atomic
  per-lookup publication and cooperative process recovery; it explicitly does
  not claim full Darwin power-loss durability.
- [#140f9466](140f9466-config-delivery-non-atomic-rollback-loss.md) concerns
  mutable user configuration delivery, not immutable generated bundle trees.

## What probably needs to be done

- Define whether direct developer bundles need a power-loss guarantee or only
  a documented rebuild path.
- Verify where Darwin `F_FULLFSYNC` is supported for staged files and directory
  entries, and define a fail-closed policy for unsupported filesystems.
- Determine whether retaining one verified previous generation until the next
  successful run is sufficient for the supported reader and power-loss model.
- Add platform-native fault tests or a filesystem harness that can distinguish
  process interruption from unflushed namespace state.

## Acceptance criteria

- The documented durability boundary matches the actual Darwin and Linux
  synchronization primitives.
- If power-loss recovery is promised, every cleanup boundary retains a verified
  old or new generation after the supported fault model.
- Unsupported filesystems fail before publication or provide an explicit,
  tested rebuild-only result.
- Normal direct builds leave no unbounded retained generations.

## Sources

- `tools/bundle_publication.py`
- `tools/bundle_rename.py`
- `docs/tickets/66ab4af8-make-bundle-publication-atomic.md`
- <https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html>
