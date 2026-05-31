---
name: testing-strategy
user-invocable: false
description: Apply the testing pyramid and low-infrastructure-first principle to choose which test(s) to write for any non-trivial code change, bug fix, or new behaviour. Triages by what the change touches (behaviour boundary, integration boundary, user-facing path), names the appropriate test level, and flags anti-patterns (testing implementation, flaky e2e, weakening assertions, slow suites). Tests are part of the change itself, not a follow-up. Pairs with the CLAUDE.md TDD bullets — bug-fix failing test first, Red→Green→Refactor, default to fast isolated tests.
when_to_use: Trigger on any non-trivial code change — implementing a feature, fixing a bug, refactoring behaviour, modifying logic that other code depends on. Also runs when about to write a test directly, planning a change touching multiple layers, reviewing a test suite for shape and quality, or evaluating whether an existing test is at the right level. The default assumption is that a behavioural change ships with its test, not without one — engage this skill as part of planning the change, not as a separate later step.
---

# Testing strategy

Decide **which test(s) to write** for a change so that regressions are caught at the cheapest, fastest level possible. Companion to the CLAUDE.md TDD bullets — those state the principles; this skill is the triage procedure.

## Triage — which level fits this change

Walk the change against these questions in order. Stop at the first match.

1. **Is the change a bug fix?** Write a failing test that **reproduces the bug** at the lowest level where the bug is observable. If the bug surfaced through the UI but the root cause is in a function — the test goes at the function level, not the UI level.
2. **Does the change touch a single function / class / module with a defined contract?** → Unit test. Cover the new branches, edge cases, and the specific input that triggered the change.
3. **Does the change touch the contract between two of your own components (function A calls function B, service A talks to service B in the same process)?** → Unit test with a real B if B is fast and pure; sociable test (real collaborators where they are fast) if mocking would test the mock instead of the contract.
4. **Does the change touch an integration boundary that you cannot meaningfully verify at unit level — DB schema, external API contract, message queue serialisation, file format?** → Integration test against the real thing (or a high-fidelity fake / contract test like Pact). Do not write an e2e test for this — the e2e cost is wrong tool.
5. **Is the change in a user-facing path where the user journey itself is the contract being verified?** → End-to-end test, narrow and focused. Cover the golden path and one or two critical error paths. Do not e2e-test variations that are already covered at lower levels.
6. **Cannot reach a clean level (e.g. legacy code with tangled dependencies)?** → Characterisation test at the smallest reachable surface. Note the technical debt in `surface-ticket` if the legacy structure is the real blocker.

## Pyramid levels — when each is right

| Level | Right when | Wrong when |
|---|---|---|
| **Unit** (single function/class, no I/O) | Logic with branches, calculations, state transitions, parsers, validators, pure transformations | Used to test "did the wiring connect" — that is integration concern |
| **Integration** (real DB / real external in test scope) | DB query correctness, ORM mapping, schema migrations, external API contract, serialisation across process boundary | Used as substitute for missing unit tests on logic — too slow, too coupled |
| **End-to-end** (full user-facing flow) | Golden-path user journey, regression of a critical flow that previously broke in production | Used to verify business rules — those belong at unit level; one e2e per rule means slow suite |
| **Characterisation** | Locking in current behaviour of legacy code before refactor | Used as the only level forever — characterisation tests do not document intent, they document accident |

Default ratio across a stack: many more unit than integration, many more integration than e2e. Google's 70/20/10 (unit/integration/e2e) is a reasonable starting target — the **shape** matters more than the exact numbers.

## When the pyramid bends

Two legitimate deviations from a strict pyramid:

1. **Fowler exception (Practical Test Pyramid):** if higher-level tests are fast, reliable, and cheap to modify in this codebase, lower-level coverage is less critical for the same surface. Example: a thin microservice whose entire behaviour is a 50-line route handler — one integration test per route may genuinely cover what would otherwise need 30 unit tests.
2. **Testing trophy (Kent C. Dodds) for UI / component-heavy frontend:** integration tests through the component layer often give better ROI than unit-testing every internal hook or render branch separately. Applies to frontend; **does not generalise to backend / API / library code**.

State the deviation explicitly when you take it ("using integration as primary because the route handler is the entire behaviour") — do not silently drift up the pyramid.

## Anti-patterns

- **Testing implementation, not behaviour.** Asserting on internal method calls, private state, or call sequence rather than the output the caller observes. Makes refactoring expensive and produces false-positive failures on safe internal changes. Per Fowler: "Test for observable behaviour instead."
- **Weakening assertions to make a test pass ("greenifying").** Changing `assertEquals(expected, actual)` to `assertNotNull(actual)` because the test is failing. Inverts the Red→Green→Refactor contract. The fix is in the code or in the test's intent, not in loosening the check.
- **Mocking what you do not own and then trusting the mock.** Mocking an external API to a behaviour the real API does not exhibit. The test passes; production fails. If the contract matters, integration-test the real thing or use a contract test (Pact, Spring Contract).
- **Flaky tests left in place.** A test that passes/fails non-deterministically is worse than no test — it trains the team to retry rather than investigate. Quarantine immediately (skip + `surface-ticket`) and fix the determinism, do not "rerun until green."
- **Slow suites dominated by e2e.** When the full suite takes 30+ minutes, developers stop running it locally. CI becomes the only gate; feedback loops break. Move logic-level checks down to unit / integration.
- **Test-after that confirms what exists.** Writing the test after the code, especially for the same scenario the author had in mind, confirms the implementation exists rather than that it does the right thing. For new behaviour requiring guarantee → test-first. For exploratory work → write the test once you know what guarantee you need, then refactor the spike code against it.
- **`.skip` / `.only` / `xit` left in committed code.** Already banned by the [`no-suppression-markers` skill](../no-suppression-markers/SKILL.md). If a test truly cannot run now, the failure or the need is captured via [`surface-ticket`](../surface-ticket/SKILL.md), not a marker.

## Verification before declaring done

Run the suite and **observe the result with your own eyes**. CI status is not a substitute — it confirms green at a delayed moment in time, not that you saw your test fail before the fix and pass after. Specifically:

1. Run the test you added. Confirm it **fails** on the unfixed code path (for bug fix) or **fails** before the new behaviour exists (for new feature).
2. Apply the fix / implementation.
3. Run the test again. Confirm it **passes**.
4. Run the surrounding suite (the package or module level). Confirm nothing else broke.
5. If a regression appears in a test unrelated to the change — investigate, do not assume flakiness.

## Sources

- Kent Beck, *Test-Driven Development: By Example* (2002) — Red → Green → Refactor; failing test before bug fix; observe-the-result discipline.
- Martin Fowler, *TestPyramid* (martinfowler.com/bliki/TestPyramid.html) — pyramid shape; high-level exception when fast and reliable.
- Martin Fowler, *Practical Test Pyramid* (2018) — test observable behaviour; sociable vs solitary tests; CDC layer.
- Google Testing Blog, *Just Say No to More End-to-End Tests* (2015) — 70/20/10; flaky e2e; slow-suite consequences.
- Mike Cohn, *Succeeding with Agile* (2009) — original pyramid concept.
- Gerard Meszaros, *xUnit Test Patterns* (2007) — test smells catalogue (overspecified software, fragile test, slow test).
- Kent C. Dodds, *Testing Trophy* — frontend-specific deviation from classical pyramid (do not generalise).
