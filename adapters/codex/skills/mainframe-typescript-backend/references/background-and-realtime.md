# Background jobs and realtime

- Preserve the established queue or scheduler. Do not add infrastructure for
  work that can remain safely in process.
- Assume retries, duplicates, delays, and stale payloads. Make handlers
  idempotent where duplicate effects are harmful.
- Acknowledge only after the required durability point. Bound retry and backoff;
  classify permanent failures instead of looping indefinitely.
- Keep payloads small, version-tolerant, and secret-free. Re-read canonical
  state when stale payload data could cause harm.
- Authenticate WebSocket connections and authorize every privileged event.
  Validate event payloads and handle reconnects and duplicates.
- Define room, subscription, presence, and fan-out ownership. One-process memory
  does not work across replicas.
- Test business rules without a live broker when transport semantics are not
  the changed risk.

Sources: [BullMQ](https://docs.bullmq.io/),
[pg-boss](https://github.com/timgit/pg-boss),
[NestJS queues](https://docs.nestjs.com/techniques/queues),
[Socket.IO delivery](https://socket.io/docs/v4/delivery-guarantees).
