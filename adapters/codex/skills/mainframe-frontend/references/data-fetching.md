# Browser data and server state

- Preserve the active data mechanism: framework-native server fetching, TanStack Query, SWR, Apollo, URQL, a project HTTP client, or direct `fetch`. Do not add a cache library for a single request.
- Keep cache ownership singular. Do not copy remote snapshots into another global store. A form or optimistic draft may intentionally diverge, but it needs an explicit reconciliation path.
- Represent every user-reachable state: initial loading, empty success, populated success, recoverable error, pending mutation, stale data, and offline state when applicable. Use the library's native state model instead of rebuilding it.
- Query keys, tags, or cache identities must include every parameter that changes the result and must not leak tenant or user data across identities.
- Use optimistic UI only when rollback or reconciliation is defined and the operation is safe to project. Cancel or sequence conflicting work according to the active library's documented behavior.
- Make cancellation, timeouts, retries, pagination, invalidation, and revalidation follow the product contract. Do not disable freshness behavior globally to hide a local bug.
- Validate network data when it crosses an uncertain or consequential contract. For an owned generated client or tightly tested internal contract, avoid duplicating runtime validation without a demonstrated risk.

Sources:
- TanStack Query — https://tanstack.com/query/latest
- SWR — https://swr.vercel.app/
- Next.js data fetching — https://nextjs.org/docs/app/getting-started/fetching-data
- Fetch API — https://developer.mozilla.org/docs/Web/API/Fetch_API
