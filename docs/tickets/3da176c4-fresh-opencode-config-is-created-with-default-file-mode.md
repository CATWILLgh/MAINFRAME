---
id: 3da176c4
title: Fresh OpenCode config is created with the process default file mode
status: approved
priority: medium
component: opencode-configuration
discovered: 2026-07-15
discovered-from: []
tags: ["security", "opencode", "permissions", "configuration", "installer"]
---

# 3da176c4: Fresh OpenCode config is created with the process default file mode

## What was observed

`write_config` sets the rolling backup to mode `0600`, but writes the live `opencode.json` with a normal `open(path, "w")` and never applies an explicit mode. Existing files retain their prior mode; a fresh file commonly inherits umask-derived `0644` permissions.

## Why it is a problem

The generated file can contain MCP commands, credential reference paths, provider configuration, and other user-specific state. On a multi-user machine, default-readable permissions expose more configuration than the generator's own backup policy permits.

## Why it is not a duplicate

[#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md) fixed literal secrets and permissions on the current machine. This ticket covers the still-unfixed fresh-generation behavior in the repository, which can recreate the weak mode on another installation.

## What probably needs to be done

- Create the file atomically with mode `0600` and preserve or tighten an existing file's mode according to an explicit policy.
- Verify the containing directory permissions as part of installation diagnostics.
- Keep backups at least as restrictive as the live file.

## Acceptance criteria

- A fresh generated `opencode.json` has mode `0600` regardless of umask.
- Rewriting an existing `0600` file preserves that mode.
- A pre-existing weaker mode is reported and tightened only under the documented ownership policy.
- Tests inspect modes for new file, existing file, backup, and failed write.

## Sources

- `adapters/opencode/config_writer.py:31-224`
- `adapters/opencode/build_opencode.py:315-383`
- `tools/test_opencode_config_writer.py`
- `tools/test_opencode_config_writer_failures.py`
- [#c71185b2](c71185b2-opencode-json-plaintext-api-keys.md)

## Resolution (2026-07-15)

**Implementer:** Codex primary agent
**Commit:** `76d6e92a8c2d2ff24188850e950cb39247d29701`
**Summary:** OpenCode configuration publication now serializes before filesystem mutation, creates missing parent directories with exact mode `0700`, stages live and backup bytes on the target filesystem, and publishes a fresh configuration with mode `0600` regardless of umask. Existing `0400` and `0600` modes are preserved, weaker readable modes are tightened to `0600` and reported, and inaccessible or non-regular targets are refused without mutation. Backup and cleanup failure states are explicit and tested.
**Claims to verify on audit:**
- Fresh configuration is `0600` and newly created parents are `0700` under both permissive and restrictive umasks.
- Existing `0400` and `0600` modes remain unchanged; weaker readable modes tighten to `0600`; `0200` and `0000` fail unchanged.
- Backups contain the exact prior bytes and are never less restrictive than the published live file.
- Valid and dangling symbolic links, directories, FIFOs, and non-regular backup targets are refused without changing live or backup data.
- Serialization and pre-publication failures create no live output or staging residue; a post-publication cleanup failure reports a warning and does not suppress permission-state publication.
- Dry-run creates no configuration, state, or agent output, and no live render or installation was performed.

## Audit (2026-07-15)

**Auditor:** Independent read-only subagent (`opencode_writer_final_review`)
**Verdict:** Approved
**Verified:**
- No grounded Critical, High, Medium, or Low findings remained after review.
- All 512 ordinary file-mode combinations matched the documented preservation and tightening policy.
- Symbolic-link, directory, and FIFO backup targets were refused without changing live data.
- The focused OpenCode suites passed 14/14, 26/26, 14/14, and 8/8; all 33 `tools/test_*.py` files passed.
- Repository dry-run created no output; syntax compilation, render consistency, diff hygiene, file/function limits, and suppression/debug-marker scans passed.
**Commit scope:** Only the OpenCode builder, secure writer, and focused tests were committed. User-owned `dist/claude-code/settings.json`, `.agents/`, and `.codex/` changes remained outside the commit.
**Known limit:** Concurrent writers, secure descriptor-relative parent traversal, ACL/extended-attribute/hardlink preservation, unchanged-write suppression, and cross-file transaction recovery remain tracked in `#140f9466`.
