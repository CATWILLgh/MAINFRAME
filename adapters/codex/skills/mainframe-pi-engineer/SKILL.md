---
name: mainframe-pi-engineer
description: Delegate one already-agreed bounded implementation block to a project-scoped Pi coding worker after the result, writable scope, acceptance criteria, and allowed checks are clear. Do not use for requirements discovery, architecture decisions, open-ended research, or work that still needs a user choice.
---

# Pi engineer

Keep architecture, user communication, final review, and the commit in this
primary task. Pi implements one already-agreed block in the current Git
worktree and returns structured evidence; its internal verifier is a quality
gate, not final acceptance.

For a new block, write a short JSON request inside
`.agents/runtime/pi/requests/` with this exact shape:

```json
{
  "schemaVersion": 1,
  "goal": "One observable result",
  "writePaths": ["path/or/narrow-glob"],
  "excludePaths": [],
  "invariants": ["Behavior that must remain true"],
  "acceptance": ["Concrete result that can be checked"],
  "forbiddenFutureStages": ["Later work that must not begin"],
  "checks": [{"argv": ["exact-executable", "arg"], "timeoutMs": 60000}]
}
```

Keep lists only as detailed as the block requires. Checks must be exact argv,
not inline shell, and cannot invoke Git. Run `mainframe-pi engineer --mode new
--request <project-relative-request.json>` in a persistent background terminal
session with a short initial yield. Continue useful primary-agent work instead
of polling the terminal or sleeping. The opt-in Pi completion bridge waits at
the end of the turn and resumes this task when the run has a terminal result.

For a correction to the same active block, write a packet containing exactly
`instructions`, `missingEvidence`, and `failedCheckIds` arrays, then run
`mainframe-pi engineer --mode resume --feedback
<project-relative-feedback.json>`. Omit `--feedback` only when resuming
interrupted work without new review findings.

Pi may report a concrete blocker or plan conflict as soon as continuing would
waste work. The harness sends that claim directly to a fresh verifier without
running irrelevant candidate checks. A false claim is corrected automatically
inside the same Pi session; only a verifier-confirmed `blocked` or
`plan-conflict` returns to this primary task.

Let a run finish unless it reports a real block. When the completion bridge
resumes the task, inspect the returned status, changed paths, checks, acceptance
evidence, and verifier verdict against the actual diff.
`ready-for-architect-review` means only that Pi's internal pass is complete.
Send an in-scope defect back as one precise `resume` correction. Once accepted,
create the Conventional Commit here, limited to accepted task paths and
preserving unrelated dirty or staged work. Explicitly choose `new` for the next
block; MAINFRAME archives the previous resumable state and compacts the
persistent Pi session without trying to infer acceptance from Git.

After `plan-conflict`, never send an empty resume. Provide a correction packet
when the plan must change. If independent review proves the implementation is
acceptable and only the supplied check or plan is impossible, perform the
normal diff review and commit, then explicitly choose `new` for the next block.

A provider timeout preserves the active session and owned-file record. Do not
replace the block or repeatedly retry it while the provider is unavailable;
resume it after provider recovery.

Do not copy Pi's internal pipeline into the prompt, pass profile/config/project
overrides, ask Pi to commit, or treat its verifier as user acceptance.
Do not start a second run because the first is slow, and do not spend model
turns repeatedly polling it. If the native completion bridge is unavailable,
fall back to one foreground run rather than blind timer loops.
