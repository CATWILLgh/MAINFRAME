# Redis

First determine Redis's role in the project: disposable cache, rate limiter, session store, queue transport, coordination aid, or durable-enough application state. Its eviction, expiry, persistence, and failure behavior depend on that role.

## Cache behavior

- Define freshness, invalidation, TTL, and behavior when Redis is unavailable. A cache key normally needs an expiry unless deliberate invalidation and capacity policy prove otherwise.
- Make database write and cache invalidation order explicit. Account for the window where readers may repopulate stale data; use versioned keys, write-through, an outbox, or another stronger design when the business risk requires it.
- Mitigate hot-key stampedes with single-flight work, bounded locking, early refresh, or expiry jitter where measurements show the risk.

## Atomic coordination

- Multi-command check-then-act behavior needs an atomic primitive such as one command, a server-side script, or an optimistic transaction with retries.
- For a basic ownership lock, acquire with a unique token and release only through an atomic token comparison. TTL protects liveness but does not prove exclusive correctness after pauses or expiry.
- Redis locks without fencing are coordination aids, not sufficient proof for money or irreversible exactly-once effects. Prefer a database invariant or a system with fencing for correctness-critical ownership.

## Operations

Keep high-cardinality keys bounded, inspect eviction and memory policy, and test degraded behavior. Persistence settings must match whether loss is acceptable; a cache and a source of truth need different guarantees.

## Sources

- Redis key eviction — https://redis.io/docs/latest/develop/reference/eviction/
- Redis distributed locks — https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/
- Redis transactions — https://redis.io/docs/latest/develop/interact/transactions/
- Martin Kleppmann on distributed locking — https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
