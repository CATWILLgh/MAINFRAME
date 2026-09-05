# Background and realtime work

Preserve the established queue and realtime transport. Treat an HTTP process, worker, scheduler, and Socket.IO server as separate runtimes even when they import the same application code.

## Queued work

- Put only serializable identifiers and trusted execution context into a job. Reload current durable state inside the worker rather than serializing ORM objects or request globals.
- Re-establish application, tenant, trace, and database context at job start and clear it afterward so reused workers cannot leak state.
- Define job timeout, queue lifetime, result retention, retry policy, and failure visibility from business cost. Retry only transient failures and make external effects idempotent.
- Enqueue after the owning database commit or through an outbox when the job must not observe rolled-back or missing state.
- A queue accepting a job does not prove a healthy worker consumed it. Monitor queue age, failures, worker heartbeats, and the business outcome.
- RQ behavior is version-sensitive; inspect the installed version before using uniqueness, rate limits, callbacks, or newer result APIs.

## Socket.IO and WebSockets

- Authenticate the handshake and authorize every event; connection membership alone is not continuing authorization.
- Re-establish tenant and correlation context for each event. Validate event payloads as untrusted input.
- Configure exact allowed origins where browser credentials are involved. Avoid tokens in query strings because proxies and logs commonly retain URLs.
- When several server instances own different connections, use sticky routing plus the supported message queue for rooms and broadcasts.
- Flask-SocketIO deployment mode constrains worker choice and concurrency. Verify Gunicorn, gevent or threading, monkey-patching order, proxy upgrade headers, and message-queue compatibility together rather than tuning one setting in isolation.
- Decide whether delivery is durable or best-effort. Realtime acknowledgement does not replace durable state, and notification failure after commit must not silently roll back the completed business operation.

## Sources

- RQ documentation — https://python-rq.org/docs/
- Flask-SocketIO deployment — https://flask-socketio.readthedocs.io/en/latest/deployment.html
- Flask-SocketIO implementation notes — https://flask-socketio.readthedocs.io/en/latest/implementation_notes.html
