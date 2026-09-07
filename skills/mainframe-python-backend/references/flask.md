# Flask

Trace the served application object or application factory, configuration loading, blueprint registration, extension initialization, request hooks, error handlers, and WSGI process command. Preserve the project's factory and extension ownership; repeated initialization must not duplicate handlers or registrations.

Keep request parsing, response construction, status codes, headers, sessions, CSRF, and error mapping consistent with the established public contract. Authorize the concrete object and action rather than relying only on route access.

Treat Flask's async behavior as version- and deployment-specific. Under ordinary WSGI serving, an async view still occupies a worker for the request and its event loop ends with the view. Do not spawn durable background work from that loop. Check extension compatibility before using it from an async view.

Use an ASGI adapter or async-first framework only when the existing project already establishes it or changing architecture is explicitly in scope. Do not smuggle a server-model migration into a feature fix.

Keep application and request context ownership explicit in tests, callbacks, threads, and workers. Do not retain proxies or request-scoped resources after their context ends.
