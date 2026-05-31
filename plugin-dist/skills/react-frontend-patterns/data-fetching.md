# Data fetching — TanStack Query 5

Server state lives in TanStack Query. No `useEffect(() => fetch(...), [])` patterns, no Redux-thunk replacements, no ad-hoc cache. Per upstream docs (https://tanstack.com/query/latest): TQ is **the** server-state library for React.

## Query keys — array convention, deterministic

```ts
useQuery({ queryKey: ['todos'], queryFn: fetchTodos })                       // list
useQuery({ queryKey: ['todo', id], queryFn: () => fetchTodo(id) })           // one
useQuery({ queryKey: ['todos', { status, page }], queryFn: ... })            // filtered
```

Object params are key-order-insensitive (TQ hashes deterministically). Primitive params are positional — `['todos', status, page]` ≠ `['todos', page, status]`. Pick one shape per resource and stick to it; centralise in `entities/<name>/api/queryKeys.ts`.

## Discriminated states — read `status`, not `data == null`

```ts
const { status, data, error } = useQuery(...)
if (status === 'pending') return <Skeleton />
if (status === 'error') return <ErrorBlock error={error} />
return <Cards items={data} />
```

`data === undefined` could also mean error. Branching on `status` keeps loading and error paths separate.

## Mutations + optimistic updates

```ts
const mutation = useMutation({
  mutationFn: updateTodo,
  onMutate: async (next) => {
    await queryClient.cancelQueries({ queryKey: ['todo', next.id] })
    const prev = queryClient.getQueryData(['todo', next.id])
    queryClient.setQueryData(['todo', next.id], next)
    return { prev }
  },
  onError: (_e, next, ctx) => queryClient.setQueryData(['todo', next.id], ctx?.prev),
  onSettled: (_d, _e, next) => queryClient.invalidateQueries({ queryKey: ['todo', next.id] }),
})
```

Rollback on error, invalidate on settled (success or failure). Skipping `cancelQueries` causes a race between optimistic write and a concurrent refetch.

## Pagination — cursor-based via `useInfiniteQuery`

Page-number pagination works for stable lists; for activity feeds and growing data sets, prefer cursor:

```ts
useInfiniteQuery({
  queryKey: ['feed'],
  queryFn: ({ pageParam }) => fetchPage(pageParam),
  initialPageParam: null as string | null,
  getNextPageParam: (last) => last.nextCursor ?? undefined,
})
```

## Error handling — `throwOnError` + boundary

For non-recoverable query errors (auth expired, server 500), enable `throwOnError: true` on the query (or globally) and catch at a Suspense / ErrorBoundary one level up. Per-query `try/catch` inside components is an anti-pattern — it duplicates UI between «loading», «empty», and «error».

## What NOT to do

- **Do not store query data in a separate Zustand/Jotai store** — `queryClient.getQueryData(key)` IS the store.
- **Do not chain `useEffect` to copy `data` into local `useState`** — it desyncs on refetch.
- **Do not use `enabled: !!variable && !!anotherVariable && ...`** with five clauses — extract a typed guard `const ready = isReady({ a, b, c })`.
- **Do not `refetchOnWindowFocus: false`** as default for sensitive data — staleness on focus is a real correctness issue per TQ docs.

## Sources

- TanStack Query v5 — https://tanstack.com/query/latest
- TanStack Query — Optimistic Updates — https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates
- TanStack Query — Query Keys — https://tanstack.com/query/latest/docs/framework/react/guides/query-keys
