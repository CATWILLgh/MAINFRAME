# Django

Trace the effective settings module, installed app, URL configuration, middleware order, view or viewset, serializer or form, permission path, model manager, and migration state. Preserve established Django and Django REST Framework boundaries; do not introduce DRF into a plain Django path or bypass it where it owns the contract.

Keep authorization close to the concrete queryset, object, and mutation. Validate forms, serializers, and request data at their actual boundary. Preserve response shape, pagination, exception mapping, content negotiation, CSRF, session, and host behavior when those are part of the existing contract.

Treat QuerySets as lazy and inspect evaluation points, relation loading, annotations, ordering, and database round trips. Avoid hidden N+1 behavior, accidental full-table materialization, and business decisions based on stale instances.

Match the installed Django version's async support. Do not call async-unsafe synchronous APIs from an async context. Keep transaction-dependent ORM work in a supported boundary rather than disabling async safety. Verify middleware and deployment mode because sync/async adaptation can change concurrency and performance.

Create migrations through the project's native workflow when schema change is in scope. Review operations and data migrations for forwards behavior, compatibility with rolling code versions, lock or rewrite risk, reversibility, and historical model correctness. Do not edit applied migration history casually.
