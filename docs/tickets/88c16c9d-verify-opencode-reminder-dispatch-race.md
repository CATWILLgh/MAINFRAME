---
id: 88c16c9d
title: Verify and define safe OpenCode reminder dispatch
status: needs-refinement
priority: low
component: opencode-memory
discovered: 2026-07-15
discovered-from: []
tags: ["opencode", "concurrency", "reminder", "verification"]
---

# 88c16c9d: Verify and define safe OpenCode reminder dispatch

## What was observed

On `session.idle`, `sendReminder()` records `lastAttemptBytes`, awaits an external
detector process for up to eight seconds, then calls `client.session.prompt()`.
It does not re-check that the session is still idle or serialize against a user
message or another plugin dispatch during that window.

This is a plausible race from code inspection, but the audit did not reproduce
it against the installed OpenCode CLI or Desktop. It therefore remains a
verification ticket rather than a confirmed implementation defect.

## Why it is a problem

If the session resumes while the detector is running, an automated reminder may
create an overlapping assistant turn, duplicate response, or unexpected billed
model call. Changing dispatch semantics without reproduction could also create
new regressions, so the actual host behavior must be established first.

## Why it is not a duplicate

- [#c2ff95ad](c2ff95ad-account-for-opencode-substantive-activity.md) decides when
  a reminder is warranted; this ticket concerns dispatch after that decision.
- [#b21de3c2](b21de3c2-serialize-antigravity-advisory-queue.md) uses a different
  runtime and file-backed state mechanism.

## Context needed

- Whether `session.idle` remains authoritative until a plugin handler returns.
- Whether `client.session.prompt()` is serialized with concurrent user prompts.
- Whether OpenCode exposes a current session-status or compare-and-dispatch API.
- Behavior differences between CLI 1.17.15 and Desktop 1.18.1.

## What probably needs to be done

1. Build a controlled real-runtime experiment that resumes the session during
   the detector await window.
2. Capture session events and resulting message parentage without using secrets.
3. If reproduced, add a per-session dispatch guard and immediate state re-check.
4. Prefer an asynchronous or context-only API if the current plugin contract
   provides one; requires verification against official/current source.

## Acceptance criteria

- The race is either reproduced with exact event ordering or closed with evidence
  that the host serializes the operation safely.
- If reproduced, one idle interval produces at most one reminder turn.
- A user message arriving during detector evaluation always takes precedence.
- Tests cover detector delay, repeated idle events, session deletion, and failure.
- CLI and Desktop behavior is recorded separately.

## Sources

- `adapters/opencode/plugins/mainframe-memory.js:106-130`
- `adapters/opencode/plugins/mainframe-memory.js:144-162`
- `tools/test_mainframe_memory.mjs:181-239`
- <https://opencode.ai/docs/plugins>
