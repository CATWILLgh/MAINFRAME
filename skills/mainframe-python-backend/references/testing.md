# Testing

Use the project's existing runner, fixtures, factories, async plugin, framework clients, and infrastructure decisions. Do not impose pytest, unittest, a database, a broker, or a container strategy.

Choose the smallest faithful boundary for the changed risk. Pure business rules may need direct tests; transport contracts need the owning framework boundary; persistence, locking, constraints, and migrations may require the actual database engine; worker delivery may require the real queue semantics; lifecycle behavior may require a real process.

Start with focused evidence that fails for the reported behavior when practical. Then run the repaired proof and the nearest relevant fast regression checks. Keep broad, expensive, compatibility, and full-system suites for CI or an explicitly requested full pass unless the change's risk cannot be established otherwise.

Preserve production validation, authentication, authorization, middleware, dependency injection, transaction boundaries, and serialization in tests. A direct function call is not proof of an HTTP contract, and a mocked repository is not proof of database semantics.

Make async and concurrent tests deterministic. Coordinate starts with barriers or events instead of sleeps, assert the resulting invariant, and clean up tasks, contexts, sessions, and resources. Ensure ASGI lifespan runs when startup or shutdown owns the behavior under test.

Keep fixtures minimal and non-secret. Avoid weakening assertions, skipping the relevant path, over-mocking the behavior under test, or accepting snapshots that hide meaningful contract changes. Report the exact level of evidence obtained and every untested boundary.
