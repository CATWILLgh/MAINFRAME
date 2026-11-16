---
name: mainframe-testing
description: Design, run, or repair tests and CI. Use for TDD, regressions, performance, database migrations and checks, and GitHub/GitLab test gates.
---

# Own the behavior and its verification

Use this method for authorized behavior changes and test or CI work. Pair
it with stack-specific guidance when the changed contract needs it.

- State the observable result and protected side effects. Choose the smallest
  faithful boundary. For a behavior change, see the focused failure for that
  behavior, make the complete correction, then refactor with checks green.
  Reuse an existing red. Setup, syntax, and dependency failures are not red
  evidence. For prose and reversible low-impact changes use direct validation.
- Cover reachable failure, rejection, retry, concurrency, and cleanup as
  relevant. Assert the real contract. Preserve meaningful coverage, report
  failures, and diagnose flakes instead of repeating them until green.
- Use focused checks and the nearest fast suite. Broaden for changed risk,
  integration, or an actual gate. Keep the local loop in-process or on verified
  isolated PostgreSQL where needed. Use CI for other real dependencies and
  expensive, compatibility, or end-to-end checks by default. Broaden locally
  only with authority. A substitute engine cannot prove real semantics.

Use `mainframe-test-audit` to assess an existing test system for an assigned
audit or a concrete escaped regression, false green, flake, or cost problem.
An audit-only assignment stays read-only. When both audit and repair are
authorized, establish findings first, then use this method for the repair.

## Load the method needed now

Read only the reference for the current decision. Reuse guidance still in context.

| Decision | Reference |
| --- | --- |
| Project strategy, test levels, or the project verification map | [Shared strategy](references/strategy.md) |
| Changed latency, resource use, database access, index usefulness, or shared background capacity | [Performance and database checks](references/performance.md) |
| Schema, migration, index, constraint, or data rollout design and verification | [Migration method](references/migrations.md) |
| Red/green/refactor, regression design, or an inherited implementation | [Behavior and TDD](references/tdd.md) |
| Local scope, fixtures, a runaway check, PostgreSQL identity, or an unavailable dependency | [Local test boundary](references/local.md) |
| Analyzer selection, installation, reuse, or hook execution | [Small tool profiles](references/tooling.md) |
| Required CI checks, triggers, cost, caching, failures, or evidence ownership | [CI contract](references/ci.md) |
| GitHub workflow authoring or troubleshooting | [GitHub Actions](references/github.md) |
| GitLab pipeline authoring or troubleshooting | [GitLab CI](references/gitlab.md) |


## Finish with evidence

- For behavior or CI work, connect the changed guarantee to an executable
  check, route, and pass condition in the existing project verification map.
  Reconcile only relevant gaps. Include actual latency, resource, and DB
  progress where those are the risk.
- Give delegated implementers the behavior, local/CI boundary, permitted
  infrastructure, and required proof. They report observed red/green and
  pending jobs. The primary agent checks the integrated behavior and CI coverage.
- Distinguish local results, configuration checks, actual CI for the revision
  and event, and live acceptance. If local reproduction cannot observe the
  behavior, exercise the faithful CI boundary where authorized. State any
  missing red/green evidence and the exact pending check or job.
