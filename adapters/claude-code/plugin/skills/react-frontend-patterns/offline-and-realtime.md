# Offline, PWA, and realtime behavior

- Treat IndexedDB or Dexie as durable client state with a schema, migration path, ownership, and recovery behavior. Do not use it as an invisible cache without invalidation rules.
- Define what works offline, what remains pending, when data is considered synchronized, and how conflicts are shown or resolved. Never imply a durable server success before synchronization is confirmed.
- Service-worker changes require versioning and update behavior. Avoid caching authenticated or rapidly changing responses unless isolation and freshness are explicit.
- Queue offline mutations with stable client identifiers and idempotent server contracts when duplicates can cause harm. Bound retries and expose terminal failures to the user.
- For WebSocket or Socket.IO state, handle disconnect, reconnect, duplicate events, ordering limits, and a canonical resynchronization path. Realtime events should invalidate or reconcile existing state, not create a second authority.
- Keep browser capability checks and fallbacks explicit for scanners, cameras, notifications, storage quotas, and background behavior.
- Test state transitions in process when possible; use a browser or live transport only for semantics the local test cannot prove.

Sources:
- Progressive Web Apps — https://web.dev/learn/pwa/
- IndexedDB — https://developer.mozilla.org/docs/Web/API/IndexedDB_API
- Dexie — https://dexie.org/docs/
- Socket.IO client offline behavior — https://socket.io/docs/v4/client-offline-behavior/
