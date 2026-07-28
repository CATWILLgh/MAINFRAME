---
id: f4edc31f
title: Existing suppression directives lack explicit policy justification
status: open
priority: low
component: code-quality
discovered: 2026-07-15
discovered-from: []
tags: ["code-quality", "suppressions", "typing", "lint", "policy"]
---

# f4edc31f: Existing suppression directives lack explicit policy justification

## What was observed

The current source contains live `# type: ignore` and `# noqa: E402` directives in production and test modules, while the global engineering policy requires explicit user permission for suppression markers. The audit found no nearby explanation or decision record proving why these exceptions remain necessary. Historical approval was not established, so this ticket does not assume the directives were unauthorized when introduced.

Fixture strings that intentionally test marker detection are not part of this finding.

## Why it is a problem

Unexplained suppressions hide type or import-order contract signals and contradict the standard enforced on downstream projects. Without a narrow rationale, reviewers cannot distinguish necessary interoperability from stale convenience.

## Why it is not a duplicate

- [#cb173a75](cb173a75-shared-module-for-suppression-hooks.md) covered detector-code duplication, not live suppressions in the hub.
- [#643a4490](643a4490-render-check-guard-residual-gaps.md) covered render lint gaps, not policy exceptions.

## What probably needs to be done

- Reproduce the diagnostic at each live directive and remove it through types, imports, or module structure where practical.
- If an exception is unavoidable, obtain explicit approval and record the narrow rule, diagnostic, and reason in a durable decision rather than a broad file-level suppression.

## Acceptance criteria

- Every listed directive is removed or has an explicit, narrow, reviewed justification.
- No assertion is weakened and no new suppression marker is introduced to complete the cleanup.
- Marker-detector fixtures remain intact and clearly separated from active directives.

## Sources

- `tools/validate-skill.py:36-37`
- `core/gates/detectors/comment-discipline-reminder.py:41`
- `tools/test_hooklib.py:19`
- `tools/test_markers.py:13`, with fixture-only examples at `tools/test_markers.py:31-34`
