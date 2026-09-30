# Background work and lifecycle

Every goroutine needs an owner, cancellation source, completion signal, and
cleanup path. Prefer structured groups when sibling failure should cancel the
operation. Do not start unbounded goroutines from request paths, retain request
objects after completion, close channels from the receiving side, or send on a
channel without a cancellation path.

Stop timers and tickers when their owner ends. Avoid `time.Sleep` as coordination
in production logic and tests when a channel, clock, barrier, or stored schedule
can express the condition. Bound queues and concurrent work, and define what
happens during overload and shutdown.

For polling and synchronization, make page import and its durable checkpoint
atomic when replay or skipping would violate correctness. Detect repeated or
non-advancing cursors, bound pages per pass, preserve a high-water rule suited to
the provider, and make replay idempotent. A successful page fetch without its
checkpoint is not a completed sync step.

Reload current state and authorization inside durable work rather than carrying
stale request objects. Keep worker ownership, lease/lock behavior, retry state,
and graceful shutdown explicit. During shutdown, stop admission, cancel or drain
according to the contract, and wait only within the configured grace period.

For SSE, WebSockets, or notifications, authenticate subscriptions, scope data,
bound fan-out, handle slow consumers, and design reconnect/replay behavior.
Process-local broadcast does not prove delivery across instances; notification
delivery does not replace querying durable state.
