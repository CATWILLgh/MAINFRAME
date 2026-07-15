---
id: f162d529
title: Terminate timed-out Antigravity detector trees on Windows
status: open
priority: medium
component: antigravity-hooks
discovered: 2026-07-15
discovered-from: ["c2f6d19b"]
tags: ["antigravity", "windows", "processes", "timeouts"]
---

# f162d529: Terminate timed-out Antigravity detector trees on Windows

## What was observed

The Antigravity runtime starts each detector in a new POSIX session and kills
that process group when its deadline expires. On non-POSIX systems it falls back
to `Popen.kill()`, which terminates only the detector process owned by the
bridge. A detector can itself be waiting for Ruff, Semgrep, `npx`, or another
long-running child. Antigravity officially supports Windows 10, so this is part
of the product surface rather than a theoretical portability concern.

## Why it is a problem

On Windows, a timed-out detector may leave its analyzer running after the hook
has returned. Repeated hooks can accumulate CPU, memory, network, and cache
contention even though the adapter reports the checks as finished.

## Why it is not a duplicate

- [#c2f6d19b](c2f6d19b-budget-and-isolate-antigravity-detectors.md) implements
  and verifies process-tree ownership on the current POSIX Antigravity host.
- [#d38d93a4](d38d93a4-add-antigravity-hook-diagnostics.md) covers visibility of
  detector failures, not child-process lifecycle.

## What probably needs to be done

1. Verify the supported Windows Antigravity runtime and Python version.
2. Start every detector in a Windows Job Object or an equivalent owned tree.
3. Terminate and wait for the entire tree on deadline and bridge shutdown.
4. Verify bounded output collection on the oldest supported Windows Python;
   pipe support differs across Python releases even when process launch works.
5. Preserve the current POSIX session behavior and direct-child fallback only
   for platforms where process-tree ownership is unavailable.

## Acceptance criteria

- A Windows integration test launches a detector with a grandchild, exceeds the
  allowance, and proves that neither process remains.
- Successful detector children are not terminated early.
- Spawn failure and partial-tree cleanup remain fail open for the hook result.
- POSIX process-group tests remain green.

## Sources

- `adapters/antigravity-2/gates/mainframe_runtime.py:111-171`
- [Antigravity 2.0 system requirements](https://antigravity.google/docs/getting-started)
- [Python `subprocess.Popen`](https://docs.python.org/3/library/subprocess.html#subprocess.Popen)
