# TypeScript backend testing

Read this branch when the testing baseline in `SKILL.md` is not enough to
choose the correct test boundary or keep the suite economical.

## Local development

- Keep the main loop fast and infrastructure-light. Test pure rules and use cases in process; test HTTP handlers, Server Actions, jobs, and adapters without a live service when the boundary can be exercised faithfully.
- Cover the success path and only the rejection, boundary, concurrency, or failure paths that exist in the changed contract.
- Assert outcomes and protected side effects, not incidental call order or implementation detail.
- Rework overlapping tests when behavior changes instead of adding endless near-duplicates.

## Real dependencies and CI

- Use real PostgreSQL for migrations, SQL, constraints, indexes, transactions, locking, isolation, RLS, and concurrency. Keep it outside the default fast loop unless that semantic is the changed risk.
- Use real brokers, storage, browsers, or deployed services only when their own protocol or runtime behavior is what the test must prove.
- Put broader compatibility, migration, end-to-end, and infrastructure-backed checks in CI or an explicit local command. Reuse fast local tests in CI rather than maintaining a separate duplicate suite.

Do not add arbitrary waits or duplicate the same guarantee across several test
levels merely to increase test count.

## Keep the local run bounded

Run tests in the foreground and never start another test or gate before the
first finishes. Start with the focused test. For local Vitest, default to
`--maxWorkers=2 --no-file-parallelism` unless the project is already stricter or
the test requires parallel workers. Before a broader run, check for existing
workers in this repository. Retain the PID of a long run and stop only that
process; never use broad `pkill` or `killall` against shared Node or test-runner
processes. If it hangs or overloads the machine, stop your process and report
instead of launching a duplicate. After a narrow correction, focused tests plus
typecheck or lint are enough when they cover the risk.

Sources:
- Node.js test runner — https://nodejs.org/api/test.html
- Next.js testing — https://nextjs.org/docs/app/guides/testing
- NestJS testing — https://docs.nestjs.com/fundamentals/testing
