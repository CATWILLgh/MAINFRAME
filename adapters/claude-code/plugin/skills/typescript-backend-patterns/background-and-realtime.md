# Background jobs and realtime

- Preserve the established queue or scheduler: BullMQ, pg-boss, framework scheduling, or another project-native mechanism. Do not add infrastructure for work that can remain safely in-process.
- Assume jobs may be retried, duplicated, delayed, or delivered after related state changed. Make handlers idempotent when duplicate effects would be harmful.
- Acknowledge only after the durability point required by the contract. Bound retries and backoff; classify permanent failures instead of looping forever.
- Keep payloads small, version-tolerant, and free of secrets. Re-read canonical state when stale payload data could cause harm.
- For WebSockets or Socket.IO, authenticate the connection and authorize each privileged event. Validate event payloads and handle reconnects and duplicate delivery.
- Define ownership of rooms, subscriptions, presence, and fan-out. Do not assume one-process memory works across replicas.
- Test business logic without a live broker when transport semantics are irrelevant; use the real system only for semantics the in-process test cannot prove.

Sources:
- BullMQ — https://docs.bullmq.io/
- pg-boss — https://github.com/timgit/pg-boss
- NestJS queues — https://docs.nestjs.com/techniques/queues
- Socket.IO delivery guarantees — https://socket.io/docs/v4/delivery-guarantees
