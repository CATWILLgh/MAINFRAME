# Background work and realtime delivery

- Preserve the established queue, scheduler, worker, event bus, or realtime transport. Do not add infrastructure for work that can safely remain in the owning process.
- Establish producer, durability point, consumer, retry policy, ordering, concurrency, acknowledgement, dead-letter or terminal-failure behavior, and observability before changing delivery semantics.
- Assume retries, duplicate messages, delay, reordering, and stale payloads unless the actual transport contract proves otherwise. Make handlers idempotent when duplicate effects can cause harm.
- Keep payloads minimal, version-tolerant, and free of secrets. Re-read canonical state when stale embedded data could violate current rules.
- Bound retry and backoff. Distinguish transient from permanent failures and avoid unbounded poison-message loops.
- Authenticate realtime connections and authorize each privileged subscription, room, channel, or event. Validate payloads and handle reconnect and duplicate delivery.
- Define ownership of presence, fan-out, ordering, and cleanup. Process-local memory is not shared across replicas and disappears on restart.
- Test business rules without a live broker or socket server when transport semantics are not the risk. Use the real transport only when its acknowledgement, ordering, retry, connection, or delivery behavior is the contract being tested.

Current owning references: [BullMQ documentation](https://docs.bullmq.io/), [pg-boss](https://github.com/timgit/pg-boss), [NestJS queues](https://docs.nestjs.com/techniques/queues), and [Socket.IO delivery guarantees](https://socket.io/docs/v4/delivery-guarantees).
