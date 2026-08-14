# Flask

Flask has an extension-driven ecosystem. Preserve the project's application startup, data layer, validation, authentication, and API extension instead of assuming Flask-Smorest, SQLAlchemy, Marshmallow, or Flask-JWT-Extended.

## Application and routes

- For new testable setup, prefer an application factory and initialize extensions through the application. Preserve a working established startup convention unless migration is assigned.
- Keep Blueprint boundaries aligned with the project's features or modules; do not force one blueprint per resource.
- If Flask-Smorest owns the path, use its argument and response decorators consistently. Do not introduce it for one endpoint.
- Split a module when it has distinct ownership or reasons to change, not at a universal line count.

## Request boundary

- Use the established session, JWT, or service-auth mechanism and verify operation plus resource ownership server-side.
- Use request hooks only for genuinely request-scoped setup and cleanup. Align tenant and database context with transaction lifetime.
- Do not log raw bodies, credentials, cookies, authorization headers, or secret-bearing query values.
- Translate domain and database failures at the HTTP boundary using the project's stable error contract.

## Async and background work

Flask supports async views when installed with its async extra, but each request still occupies one WSGI worker. Tasks spawned from an async view are cancelled when the view completes. Use an established durable worker for background work; moving to an ASGI-native framework is a separate architectural decision.

## Sources

- Flask documentation — https://flask.palletsprojects.com/
- Flask async behavior — https://flask.palletsprojects.com/en/stable/async-await/
- Flask-Smorest — https://flask-smorest.readthedocs.io/
