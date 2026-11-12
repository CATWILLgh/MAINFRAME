---
name: mainframe-test-audit
description: Audit existing tests or CI for missed regressions, false greens, flakiness, or excessive cost. Read-only. Test changes use the testing skill.
---

# Test-system audit

Audit the bounded existing test or CI system when its evidence, reliability,
or cost is in question. Use `mainframe-testing` to write or repair checks.
When assigned both audit and repair, establish findings first and keep any
audit-only delegate read-only.

## Apply the shared standard

Use the relevant [testing references](../mainframe-testing/SKILL.md#load-the-method-needed-now)
as evaluation criteria. Choose the shared strategy for test levels and the
verification map, TDD for sensitivity, local boundaries for fixtures and real
dependencies, tooling for analyzers, and the CI/platform guidance for
triggers, trust, required checks, and cost. For speed, resource cost, or
contention, use [performance and database checks](../mainframe-testing/references/performance.md).
If a method is unavailable, state the limit and continue the supported audit.

## Examine the evidence path

- Name the guarantee, changed risk, and scope. Inspect the owning behavior,
  tests, fixtures, lifecycle, runner commands, effective instructions, and CI
  configuration as relevant. Reconcile the project's verification map against
  observed checks and propose needed corrections. Evidence can live in
  multiple suites and formats.
- Trace the focused, fast local, real-dependency, and broader CI checks that
  actually support the claim. Check that the assertion can reject a real
  defect through the boundary where it occurs. Inspect mocks and fixtures for
  semantic fidelity, isolation, and unintended side effects. Look for assertions
  tied to private implementation, redundant work, unstable timing, and hidden
  setup or maintenance cost.
- Challenge the strongest alternative explanation. Use the owning source and
  repeatable observations for local claims, and current primary documentation
  for load-bearing external contracts. Missing historical red output alone is
  insufficient to conclude a test is weak.

| Finding | Evidence needed |
| --- | --- |
| Coverage gap | Observable regression that no existing check catches |
| Misleading green | Demonstrated pass while the claimed contract is broken |
| Reliability | Reproducible nondeterminism, order dependence, state leakage, or equivalent |
| Cost | Measured or directly observed excess and its source |

Coverage percentage, preferred ratios, style, and hypothetical improvements
are insufficient evidence on their own.

## Keep the audit read-only

Keep product code, tests, fixtures, snapshots, configuration, and the
verification map read-only. Run an existing focused check only when it supplies
needed evidence. First inspect unknown command side effects, environment, and
fixtures. Installation, services, fix modes, deployed targets, and broad or
expensive checks require the relevant assigned authority and prepared boundary.
Do not retry until green. Keep an out-of-scope observation bounded and use the
authorized project problem route or return it to the caller.

## Return actionable findings

Lead with scope and conclusion. For each confirmed issue, give the guarantee,
evidence path, reproduced failure or false-green mechanism, consequence, and
smallest acceptance condition. Keep distinct causes independently actionable.
Report observed commands and durations, disproved hypotheses, primary sources
for material external claims, and limits. Use concise evidence and keep product
acceptance and implementation with their owners. Record a durable finding only
when that authority and route are available.
