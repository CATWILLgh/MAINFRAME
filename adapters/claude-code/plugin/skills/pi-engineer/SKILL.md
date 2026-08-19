---
name: pi-engineer
description: Delegate one agreed, bounded implementation block to MAINFRAME's project-scoped Pi engineer after the result, boundaries, acceptance criteria, and allowed checks are clear. Use new for a new block and resume for corrections to the active block. Do not use for requirements discovery, architecture decisions, open-ended research, or work that still needs a user choice.
allowed-tools: Bash(mainframe-pi engineer *) Read Write
---

# Pi engineer

Keep architecture, user communication, final review, and the commit in this
primary session. Pi implements one already-agreed block in the current Git
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
not inline shell, and cannot invoke Git. Then run `mainframe-pi engineer --mode
new --request <project-relative-request.json>`.

For a correction to the same active block, write a correction packet under the
same runtime directory and run `mainframe-pi engineer --mode resume --feedback
<project-relative-feedback.json>`. The packet contains exactly `instructions`,
`missingEvidence`, and `failedCheckIds` arrays. Omit `--feedback` only when
resuming interrupted work without new review findings.

Let a run finish unless it reports a real block. Inspect the returned status,
changed paths, checks, acceptance evidence, and verifier verdict against the
actual diff. `ready-for-architect-review` means only that Pi's internal pass is
complete. If review finds an in-scope defect, send one precise `resume`
correction. If accepted, create the Conventional Commit here, limited to
accepted task paths and preserving unrelated dirty or staged work. The next
`new` block reconciles that commit and compacts the persistent Pi session.

Do not copy Pi's internal pipeline into the prompt, pass profile/config/project
overrides, ask Pi to commit, or treat its verifier as user acceptance.
