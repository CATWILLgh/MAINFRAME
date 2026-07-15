# Portable project memory contract

This layer emulates the useful parts of Claude Code project memory for runtimes
without a native equivalent. Claude Code remains on its native backend.

- Each adapter supplies its own physical `--store-root`; stores are never shared
  across runtimes.
- A project key is derived from the canonical Git common directory, so linked
  worktrees share memory. Non-Git roots use canonical filesystem paths. Multiple
  workspace roots are deduplicated and sorted before hashing. Path case is
  preserved so distinct roots cannot collide on case-sensitive filesystems.
- `MEMORY.md` is the concise startup index. Load at most the first 200 lines or
  25 KiB of valid UTF-8, whichever boundary arrives first. A truncated injected
  prompt explicitly warns that the index must be reduced.
- Detailed durable facts live in bounded sibling topic files. Names are plain
  `.md` filenames; path traversal, symbolic-link targets, and symbolic-link
  ancestors below the resolved store root are rejected.
- Writes replace a whole file under a per-target lock and atomic rename. Every
  initialized project directory carries `.mainframe-memory-version`.
- Loaded text is delimited and explicitly labelled untrusted reference data. It
  cannot override instructions or authorize actions.

The JSON command interface is `resolve`, `path`, `load`, `check`, and `write`.
All commands take `--runtime`, `--store-root`, and one or more `--workspace`
arguments. File commands take `--name`; `write` reads the full UTF-8 replacement
from standard input. An absent store is a valid empty read and never creates
filesystem state.
