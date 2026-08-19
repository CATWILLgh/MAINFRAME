---
name: mainframe-testing-strategy
description: Design or audit a cross-cutting testing strategy when test levels, suite cost, infrastructure boundaries, reliability, or regression coverage need a deliberate decision. Use for test-suite audits, slow or misleading suites, coverage spanning several components, or deciding which guarantees belong in fast local tests versus real dependencies, CI, or a deployed environment. Do not use for routine focused tests already governed by an engineering skill.
---

# Testing strategy

Build enough evidence to catch a meaningful regression without testing the same
guarantee repeatedly. Tests protect observable behavior; they are not a test
count, coverage percentage, or architectural ceremony.

Apply this strategy within the role assigned by the calling agent. An
implementation owner may create, change, and run tests while delivering the
behavior. An audit-only recipient evaluates existing evidence and records
confirmed gaps through `mainframe-ticket`; it does not implement the behavior
or author, rewrite, weaken, or suppress tests.

## Start from the guarantee

Before choosing a test, name the behavior that must remain true and the failure
the test should catch. If neither can be stated, do not manufacture a test.

- For a bug, reproduce the reported failure at the smallest surface where it is
  observable.
- For business rules, validation, calculations, permissions, lifecycle changes,
  and state transitions, prepare the failing test before implementation when the
  behavior can be expressed automatically.
- For a refactor with intentionally unchanged behavior, use existing tests or a
  focused characterization test to hold the affected contract stable.
- For exploratory work, discover the intended guarantee first, then establish
  the test before treating the result as complete.
- For documentation-only, generated, or mechanically verifiable changes, use
  the relevant deterministic check instead of inventing an application test.

Red evidence is useful only when it proves the missing or broken behavior. A
test that fails because of unrelated setup is not red evidence.

## Choose the cheapest faithful observation

Test at the lowest-cost surface that can fail for the real defect:

| Level | Use when | Avoid when |
|---|---|---|
| **Unit** | A pure rule, calculation, parser, validator, state transition, or other defined contract can be observed without I/O | The defect is in wiring or boundary semantics |
| **In-process integration** | Several owned components must cooperate, but real external infrastructure adds no relevant behavior | Mocks would replace the contract being tested |
| **Real-boundary integration** | PostgreSQL queries, migrations, indexes, transactions, locking, filesystem formats, queues, or external contracts are the risk | It merely repeats business logic already proven cheaply |
| **End-to-end** | The complete user journey, deployment wiring, or browser behavior is the contract | It enumerates business-rule variations that a lower level can prove faster |
| **Characterization** | Legacy behavior must be held stable before a safe change | It permanently substitutes for expressing intended behavior |

The shape of a suite follows its risks. Do not impose a universal ratio between
unit, integration, and end-to-end tests.

## Separate execution cost from test level

Test level and execution cost are independent. An in-process integration test
may belong in the fast local loop; a unit test with expensive process setup may
not.

- Keep the normal development loop free of containers and external services
  when they add no relevant semantics.
- Use an already available real local PostgreSQL instance for database-specific
  behavior when that is the project's established path. Do not require a
  container merely to classify a test as integration.
- Use CI or a deliberately prepared environment for deployed wiring, broad
  compatibility, and expensive system checks.
- Discover and use the project's native runner and documented conventions. Do
  not prescribe a universal wrapper or command name.

## Keep local execution bounded

- Run tests in the foreground by default. Do not start a second test or gate
  while the first is still running.
- Start with the focused test. Run one broader frontend suite only after the
  focused test is green. For local Vitest runs, default to
  `--maxWorkers=2 --no-file-parallelism` unless the project already defines a
  stricter limit or the test explicitly depends on parallel workers.
- Before a broad run, check for existing test workers for the same repository.
  If you start a long-running process, retain its PID and stop only that process.
  Never use broad `pkill` or `killall` against shared Node, Vitest, pytest, or
  similar processes.
- If a run hangs or causes unexpected load, stop the process you started and
  report the limitation instead of launching a duplicate.
- After a narrow correction, focused tests plus typecheck or lint are enough
  when they cover the changed risk; do not repeat an unchanged full suite for
  ceremony.

## Sufficient coverage

Cover the meaningful success, rejection, boundary, and failure behaviors that
the change introduces or can regress. Include a scenario only when the contract
actually has that branch.

- Prefer one strong observation over several assertions of the same guarantee.
- Do not test framework or language guarantees, trivial accessors, generated
  code, or private call sequences.
- Duplicate a critical guarantee at another level only when the second test
  closes a distinct high-cost risk, such as deployment wiring around a proven
  business rule.
- Treat coverage metrics as navigation aids. Never add tests solely to reach a
  percentage or prescribed count.

## Failure discipline

- Never weaken an assertion to make a failing test green.
- Do not trust a mock for an external contract it cannot faithfully represent.
- Do not retry a flaky test until it passes and call that verification.
- Do not introduce `.skip`, `.only`, `xit`, TODOs, or equivalent suppression.
- Fix nondeterminism caused by the current change. If a pre-existing unrelated
  flaky test prevents verification, record the observed problem through
  `mainframe-ticket` and report the limitation; do not silently suppress or
  rewrite it outside scope.

## Verification for implementation work

1. Observe the new or changed test fail for the intended reason when red
   evidence applies.
2. Implement the behavior.
3. Observe the focused test pass.
4. Run the nearest relevant fast suite using the project's native command.
5. Run a real dependency or deployed check only when the risk requires it and
   the environment is available.
6. Report only what was actually observed. Do not present an unavailable
   environment or CI status as local proof.

Automated checks establish technical confidence. Product acceptance remains a
separate observation of running functionality, business behavior, UX, and UI
by the product owner.

For a test-suite audit, use the same sequence as evidence: verify whether the
repository demonstrates the intended failure and passing state, but do not
create either state yourself when the assigned role is audit-only.

## Sources

- [Martin Fowler, Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [GitLab testing strategy](https://docs.gitlab.com/development/testing_guide/testing_strategy/)
- [Microsoft EF Core testing strategy](https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy)
- [Bazel Test Encyclopedia](https://bazel.build/reference/test-encyclopedia)
