---
name: testing-strategy
user-invocable: false
description: Designs or audits a cross-cutting testing strategy when test levels, suite cost, infrastructure boundaries, or regression coverage need a deliberate decision. Not for routine focused tests already governed by a profile's testing guidance.
when_to_use: Use for a test-suite audit, a slow or misleading suite, coverage spanning several components, or deciding which guarantees belong in fast local tests versus real dependencies, CI, or a deployed environment.
---

# Testing strategy

Build enough evidence to catch a meaningful regression without testing the same
guarantee repeatedly. Tests protect observable behaviour; they are not a count,
coverage percentage, or architectural ceremony.

Apply the strategy within the role assigned by the immediate caller. An
implementation owner may create, change, and run tests as part of delivering
the behaviour. An audit-only recipient evaluates the existing evidence and
records confirmed gaps through `ticket`; it does not implement the behaviour or
author, rewrite, or suppress tests.

## Start from the guarantee

Before choosing a test, name the behaviour that must remain true and the failure
the test should catch. If neither can be stated, do not manufacture a test.

- For a bug, reproduce the reported failure at the smallest surface where it is
  observable.
- For business rules, validation, calculations, permissions, lifecycle changes,
  and state transitions, prepare the failing test before the implementation when
  the behaviour can be expressed automatically.
- For a refactor with intentionally unchanged behaviour, use existing tests or a
  focused characterisation test to hold the affected contract stable.
- For exploratory work, discover the intended guarantee first, then establish
  the test before treating the result as complete.
- For documentation-only, generated, or mechanically verifiable changes, use
  the relevant deterministic check instead of inventing an application test.

Red evidence is useful only when it proves the missing or broken behaviour. A
test that fails because of an unrelated setup error is not red evidence.

## Choose the cheapest faithful observation

Test at the lowest-cost surface that can fail for the real defect:

| Level | Use when | Avoid when |
|---|---|---|
| **Unit** | A pure rule, calculation, parser, validator, state transition, or other defined contract can be observed without I/O | The defect is in wiring or boundary semantics |
| **In-process integration** | Several owned components must cooperate, but real external infrastructure adds no relevant behaviour | Mocks would replace the very contract being tested |
| **Real-boundary integration** | PostgreSQL queries, migrations, indexes, transactions, locking, filesystem formats, queues, or external contracts are the risk | It merely repeats business logic already proven cheaply |
| **End-to-end** | The complete user journey, deployment wiring, or browser behaviour is itself the contract | It is used to enumerate business-rule variations that a lower level can prove faster |
| **Characterisation** | Legacy behaviour must be held stable before a safe change | It becomes a permanent substitute for expressing intended behaviour |

The shape of a suite follows its risks. Do not impose a universal ratio between
unit, integration, and end-to-end tests.

## Separate execution cost from test level

Test level and execution cost are independent. An in-process integration test
may be part of the fast local loop; a unit test with expensive process setup may
not be.

- Keep the normal development loop free of containers and external services
  when they add no relevant semantics.
- Use an already available local PostgreSQL instance for database-specific
  behaviour when that is the project's established path. Do not require a
  container merely to classify a test as integration.
- Use CI or a deliberately prepared environment for deployed wiring, broad
  compatibility, and expensive system checks.
- Do not prescribe a universal wrapper command. Discover and use the project's
  native runner and documented conventions.

## Sufficient coverage

Cover the meaningful success, rejection, boundary, and failure behaviours that
the change introduces or can regress. Include a scenario only when the contract
actually has that branch.

- Prefer one strong observation over several assertions of the same guarantee.
- Do not test framework or language guarantees, trivial accessors, generated
  code, or private call sequences.
- Duplicate a critical guarantee at another level only when the second test
  closes a distinct high-cost risk, such as deployment wiring around a proven
  business rule.
- Treat coverage metrics as navigation aids. Never add tests solely to reach a
  percentage or a prescribed test count.

## Failure discipline

- Never weaken an assertion to make a failing test green.
- Do not trust a mock for an external contract it cannot faithfully represent.
- Do not retry a flaky test until it passes and call that verification.
- Do not introduce `.skip`, `.only`, `xit`, TODOs, or equivalent suppression.
- Fix nondeterminism caused by the current change. If a pre-existing unrelated
  flaky test prevents verification, record the observed problem through
  `ticket` and report the limitation to the immediate caller; do not silently
  suppress or rewrite it outside scope.

## Verification for implementation work

1. Observe the new or changed test fail for the intended reason when red
   evidence applies.
2. Implement the behaviour.
3. Observe the focused test pass.
4. Run the nearest relevant fast suite using the project's native command.
5. Run a real dependency or deployed check only when the risk requires it and
   the environment is available.
6. Report what was actually observed. Do not present an unavailable environment
   or a CI status as local proof.

Automated checks establish technical confidence. Product acceptance remains a
separate observation of the running functionality, business behaviour, UX, and
UI by the product owner.

For a test-suite audit, use the same sequence as evidence: verify whether the
repository demonstrates the intended failure and passing state, but do not
create either state yourself when the assigned role is read-only.

## Sources

- Martin Fowler, *Practical Test Pyramid* — https://martinfowler.com/articles/practical-test-pyramid.html
- GitLab Testing Strategy — https://docs.gitlab.com/development/testing_guide/testing_strategy/
- Microsoft EF Core testing strategy — https://learn.microsoft.com/en-us/ef/core/testing/choosing-a-testing-strategy
- Bazel Test Encyclopedia — https://bazel.build/reference/test-encyclopedia
