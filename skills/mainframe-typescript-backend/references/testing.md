# TypeScript backend testing

Use this reference when the backend boundary makes the faithful local evidence unclear. The global testing policy still owns routine cost, authority, and local-versus-CI rules.

## Select the observable boundary

- Test pure business rules, calculations, validation, and state transitions without transport or infrastructure when those are the complete contract.
- Test HTTP handlers, Server Actions, jobs, adapters, and serialization in process when that preserves their real validation, mapping, authorization, and side-effect behavior.
- Use the active database engine for queries, migrations, constraints, indexes, locks, isolation, or concurrency when those semantics are the changed risk and local use is authorized.
- Use a real broker, object store, browser, or deployed service only when its own delivery or runtime behavior is the contract and the environment is explicitly available.
- Verify generated clients, OpenAPI, emitted files, serialized output, and migration artifacts at their real consumer boundary rather than only checking their source generator.

## Protect the behavior economically

- Use a pre-change failing reproduction when practical and useful for the changed
  risk, confirming its failure reason. Do not manufacture a red run when direct
  inspection provides stronger evidence.
- Cover the meaningful success, rejection, boundary, concurrency, and failure branches introduced by the contract; do not enumerate branches that do not exist.
- Assert observable outcomes and protected side effects rather than private call order or implementation structure.
- Preserve deterministic control over time, retries, scheduling, and interleavings. Do not replace synchronization claims with arbitrary waits.
- Reconcile overlapping tests when behavior changes instead of accumulating near-duplicates.
- Do not trust a mock for a contract it does not implement, update snapshots blindly, weaken types or assertions, retry flakes until green, or suppress a failing path.

Run the focused proof and relevant fast package checks. Establish command scope
and side effects from its script, configuration, and fixtures when unknown or
changed; reuse that evidence for subsequent runs of the same check.

Current owning references: [Node.js test runner](https://nodejs.org/api/test.html), [Next.js testing](https://nextjs.org/docs/app/guides/testing), and [NestJS testing](https://docs.nestjs.com/fundamentals/testing).
