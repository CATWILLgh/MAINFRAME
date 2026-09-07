# Background work and realtime

Identify the project's actual execution system and delivery guarantee before changing a task, scheduler, consumer, or realtime path. Preserve queue, worker, scheduler, retry, routing, serialization, and observability conventions rather than introducing a second mechanism.

Persist business state before enqueueing dependent work, or use the project's outbox or after-commit mechanism. Design handlers for duplicate delivery and partial completion. Give retries a bounded policy, classify permanent failures, preserve stable identities, and avoid repeating irreversible side effects.

Pass identifiers and minimal durable data across process boundaries. Re-load current state and authorization context in the worker. Do not pass live ORM sessions, request objects, context proxies, unbounded payloads, or secret values through the queue.

Own database sessions, clients, context variables, and event loops per worker or task as required. Clean them up after success, failure, cancellation, and retry. Verify graceful shutdown and what happens to in-flight work.

For WebSockets, server-sent events, and socket libraries, authenticate the connection, authorize each subscription and action, validate messages, bound size and rate, handle reconnect and duplicate events, and define behavior across multiple instances. Process-local connection maps or broadcasts are not cluster-wide delivery proof.
