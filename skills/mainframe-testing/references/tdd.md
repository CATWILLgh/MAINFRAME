# Behavior-driven red, green, refactor

1. Identify the externally meaningful rule and its owning path. Use accepted requirements, current implementation contracts, and relevant authoritative documentation; resolve a missing product decision rather than encoding a guess into a test.
2. Choose the smallest faithful boundary. For an existing defect, reproduce it with the existing test or a focused new regression before touching production behavior. For a new capability, express its intended observable result first.
3. Run that focused test and inspect why it fails. It must observe the missing or wrong behavior, not missing dependencies, a broken fixture, a syntax error, or a different pre-existing failure. Preserve enough evidence to explain the original defect; a transcript of every command is unnecessary.
4. Implement the smallest complete change across affected owners. Keep validation, authorization, serialization, transaction and side-effect boundaries real where they are the contract under test.
5. Run the regression and related fast checks. Once green, refactor if it improves the result and recheck the affected behavior. Extend tests for material branches exposed by the change, without writing one test per implementation line.

## Faithful tests

- Use deterministic time, seeded randomness, controlled scheduling and isolated data. Synchronize concurrent work with barriers/events or observable conditions, not arbitrary sleeps.
- Replace external collaborators at a stable boundary with explicit success, failure and ambiguous-outcome behavior. Do not mock the component whose semantics are being claimed.
- Assert observable outcomes, including rejected side effects and cleanup. A call count can support an idempotency claim but cannot by itself prove durable business state.
- Test actual database constraints, transactions and migrations on the correct engine. Test serialization and generated artifacts through what their consumers receive.
- Make test names and failures explain the contract. Keep fixtures minimal; avoid entire production dumps, credentials, universal helper abstractions and large unrelated setup.
- Preserve meaningful regression coverage during refactoring. A changed requirement can legitimately change a test; document its basis rather than rewriting expectations to match a bug.

## Exceptions must preserve truth

For documentation, static metadata or low-impact reversible edits, use a direct semantic, schema, link or configuration check when it is stronger than a manufactured behavioral test. Do not add tests that merely repeat the edited prose.

If implementation already exists, do not claim test-first history. Demonstrate regression sensitivity on an isolated disposable baseline/revert when cheap and authorized, or report that the pre-change failure was not observed. Never revert unrelated work or deliberately break a shared checkout to stage a red run.

When only CI can observe the real dependency, write or select that test for CI. Obtain baseline and changed-revision evidence there when authorized; otherwise label it unrun. A local contract fake can test orchestration but is not the missing integration proof. Read-only investigators may inspect or run existing permitted evidence, never repair code or tracked tests merely to achieve this method.

Escaped regressions, flakiness or suspicious test cost can trigger `mainframe-test-audit` for an audit of the existing system. Do not require a separate audit for each ordinary code change.

Source: [Martin Fowler on TDD](https://martinfowler.com/bliki/TestDrivenDevelopment.html). The operating boundaries above are MAINFRAME policy, not a claim that one practice guarantees correctness.
