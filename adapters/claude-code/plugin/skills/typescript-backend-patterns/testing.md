# TypeScript backend testing

Use the project's native runner and the smallest faithful test that can catch the changed behavior's regression.

## Local development

- Keep the main loop fast and infrastructure-light. Test pure rules and use cases in process; test HTTP handlers, Server Actions, jobs, and adapters without a live service when the boundary can be exercised faithfully.
- For a bug or changed business rule, observe a focused test fail for the intended reason before the fix when practical, then pass.
- Cover the success path and only the rejection, boundary, concurrency, or failure paths that exist in the changed contract.
- Assert outcomes and protected side effects, not incidental call order or implementation detail.
- Rework overlapping tests when behavior changes instead of adding endless near-duplicates.

## Real dependencies and CI

- Use real PostgreSQL for migrations, SQL, constraints, indexes, transactions, locking, isolation, RLS, and concurrency. Keep it outside the default fast loop unless that semantic is the changed risk.
- Use real brokers, storage, browsers, or deployed services only when their own protocol or runtime behavior is what the test must prove.
- Put broader compatibility, migration, end-to-end, and infrastructure-backed checks in CI or an explicit local command. Reuse fast local tests in CI rather than maintaining a separate duplicate suite.

Never weaken assertions, hide failures, add arbitrary waits, or leave skipped tests and temporary markers.

Sources:
- Node.js test runner — https://nodejs.org/api/test.html
- Next.js testing — https://nextjs.org/docs/app/guides/testing
- NestJS testing — https://docs.nestjs.com/fundamentals/testing
