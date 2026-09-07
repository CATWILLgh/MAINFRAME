# Concurrency and tenancy

Identify the actual concurrency model: threads, asyncio tasks, processes, greenlets, workers, or a combination. Scope mutable state, database sessions, request context, clients, and caches to the boundary their libraries support. Never infer process-wide safety from single-request tests.

Keep blocking work out of event loops and avoid awaiting while holding a synchronous lock or scarce resource unless the design requires it. Use structured cancellation and cleanup for spawned tasks. Handle timeouts and cancellation without leaving transactions, semaphores, leases, or context state behind.

Use `ContextVar` only for context local to an execution flow, not as a durable store or authorization source. Set and reset it with tokens at the owning boundary. Verify propagation into threads, callbacks, background jobs, and tests instead of assuming it.

Protect concurrent state transitions with database constraints, compare-and-set updates, transactions, locks, idempotency keys, or other mechanisms supported by the actual store. Define retry scope and termination for serialization failures, deadlocks, optimistic conflicts, and duplicate delivery.

Derive tenant identity and accessible scope from trusted server-side context. Apply it to every read, write, relation, cache key, background payload, export, and realtime subscription. If the project uses database-enforced isolation, verify connection-pool reset and transaction-local context; do not assume row-level security exists or add it incidentally.
