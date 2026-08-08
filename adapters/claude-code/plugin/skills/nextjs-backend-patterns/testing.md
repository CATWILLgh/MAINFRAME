# Testing — Route Handlers & Server Actions

Per the hub `testing-strategy` skill (tier / level + TDD). Next backend tests are mostly Tier-1 (no real env): unit / integration with a mocked data layer.

## Every Route Handler / Server Action: 4 scenarios

- **Happy path** — valid input + authorized → expected result + status.
- **Unauthorized** — no / wrong session → 401 / 403 (or thrown Unauthorized), no data touched.
- **Forbidden resource** — authed but not the owner (IDOR) → 404 / 403.
- **Invalid input** — Zod rejects → 422 / 400, no business logic ran.

## How

- Import the `GET` / `POST` (or the action) directly and call it with a constructed `NextRequest` / args; assert the returned `Response` / value. No HTTP server needed at unit level.
- Mock the DAL / `auth()` to drive the authorized-vs-not branches; mock the ORM (or an in-memory / `testcontainers` DB for integration).
- **Caching contract:** when an action revalidates, spy that `revalidateTag` / `revalidatePath` was called — the contract is "fresh after mutation."
- Run locally and observe the result; do not weaken assertions to make a test pass.

## Sources

- Next.js testing — https://nextjs.org/docs/app/guides/testing
- hub `testing-strategy` skill (tiers, TDD, anti-patterns).
