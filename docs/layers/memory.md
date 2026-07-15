# Layer: Portable memory

> Claude Code owns the reference behavior. MAINFRAME emulates only the public,
> stable contract for runtimes without native project memory; it does not copy
> undocumented extraction or consolidation behavior.

## Ownership

Memory is not a new activation mechanism. It is a small data contract used by
always-on runtime instructions and lifecycle hooks:

- `core/memory/` owns project identity, bounded reads, validation, atomic
  writes, and the command-line interface used by adapters.
- `core/gates/detectors/memory-reminder.py` owns the host-neutral decision to
  remind after a substantive session.
- Each adapter owns context injection, lifecycle translation, and its physical
  store root.

Physical stores stay separate because each runtime has a different trust and
permission boundary:

| Runtime | Backend |
|---|---|
| Claude Code | Native `~/.claude/projects/<repository-id>/memory/`; MAINFRAME does not replace it |
| Antigravity 2.x desktop | `~/.gemini/antigravity/mainframe-memory/projects/<project-id>/` |
| OpenCode | `~/.local/share/opencode/mainframe-memory/projects/<project-id>/` |
| Codex | Native runtime behavior; no MAINFRAME emulation in this phase |

The contract and implementation are shared; the persisted bytes are not.

## Public contract

- `MEMORY.md` is a concise index. Detailed knowledge lives in named Markdown
  topic files and is read on demand.
- Automatic context receives the first 200 lines or first 25 KiB of
  `MEMORY.md`, whichever boundary is reached first. UTF-8 truncation is
  deterministic and never emits a partial code point.
- An oversized index is reported explicitly. Adapters must not silently imply
  that omitted content was loaded.
- Store only durable, reusable facts: user preferences, project constraints,
  stable decisions with reasons, and hard-won operational knowledge.
- Current plans, task progress, transient debugging state, credentials, and
  conversation summaries are not memory.
- New facts supersede stale or contradictory entries. Repetition is not a
  substitute for relevance.
- "Nothing to save" is a normal outcome. The reminder is selective, throttled,
  and must not create a compulsory extra turn on every stop.

Per the Claude Code memory documentation, native auto-memory uses the same
`MEMORY.md` plus topic-file shape and automatically loads the first 200 lines
or 25 KiB: <https://code.claude.com/docs/en/memory>.

## Project identity

For a Git project, the key derives from the canonical absolute Git common
directory. Therefore linked worktrees share memory. Symbolic links are resolved,
but path case is preserved so distinct roots cannot collide on case-sensitive
filesystems. A non-Git workspace falls back to its canonical workspace root.
Multiple Antigravity workspace roots are sorted and combined into one
deterministic identity.

The identity is intentionally machine-local and location-derived. Moving or
cloning a repository creates a new store; migration is explicit rather than an
automatic cross-project merge.

## Injection boundary

Loaded memory is untrusted reference data, not an instruction source. Every
adapter must:

1. wrap it in an unambiguous sentinel-delimited block;
2. state the physical source and truncation state;
3. state that content inside cannot override system, developer, user, project,
   or hub instructions;
4. avoid adding the same block twice to one system-context array;
5. fail open when the helper is unavailable or the store is invalid.

Antigravity uses `PreInvocation` `ephemeralMessage`; OpenCode uses
`experimental.chat.system.transform` and repeats the same bounded context in
the compaction hook. Antigravity's public hook contract and desktop/CLI data
split are documented at <https://antigravity.google/docs/hooks>. The OpenCode
system-transform and compaction signatures are pinned by the installed
`@opencode-ai/plugin` type declarations and covered by Tier-1 adapter tests.

## Write safety

- Topic names are a narrow filename grammar; path separators and traversal are
  rejected.
- Indexes, topics, and lock targets may not be symbolic links.
- Writes take a per-store lock and replace a same-directory temporary file
  atomically.
- The store has a version marker. Unknown versions and corrupt metadata fail
  closed for writes and fail open for context injection.
- The helper validates size before replacing the old file, so a rejected write
  cannot partially modify memory.

## Non-goals

- Importing or mutating Antigravity Knowledge Items.
- Automatic model-free fact extraction from transcripts.
- One shared physical database across runtimes.
- Reproducing undocumented Claude Code server-side consolidation.
