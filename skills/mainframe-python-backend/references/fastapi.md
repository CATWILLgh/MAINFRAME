# FastAPI

Trace the effective ASGI application, router inclusion, prefixes, dependencies, middleware, exception handlers, response models, and lifespan wiring. Multiple application objects or mounted sub-applications may coexist; identify the one served by the actual process command.

Keep transport parsing at the edge and business rules in the established service or domain layer. Use request and response models deliberately; response filtering, aliases, status codes, headers, and documented error bodies are public contract behavior.

Choose `def` or `async def` from the libraries actually called. Await native asynchronous I/O. Keep blocking I/O out of the event loop using the project's established boundary; do not assume ordinary utility functions are automatically moved to a thread pool.

Own long-lived clients, pools, and shared resources through the application's established lifespan. Construct and close event-loop-bound objects in the correct loop. Check mounted applications and tests because their lifespan behavior may differ.

Treat in-process background tasks as process-local completion work, not as a durable queue. Work that must survive restarts, coordinate across instances, retry reliably, or outlive a request belongs in the project's durable worker mechanism.

Verify security dependencies against the concrete resource and action. Do not treat a valid token, a populated user object, or router-level authentication as sufficient authorization.
