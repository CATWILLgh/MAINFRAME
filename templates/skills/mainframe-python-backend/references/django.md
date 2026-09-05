# Django and Django REST Framework

Preserve the project's app boundaries and API layer. Django REST Framework is optional; use its guidance only when it owns the active path.

## Structure and behavior

- Split or create an app only when ownership and dependency direction become clearer, not to satisfy a generic layout.
- Keep non-trivial workflows outside transport-specific views. Follow an existing service, model-method, command, or domain convention instead of introducing a second one.
- Use `ModelViewSet` only when full CRUD is intended; use narrower generic or explicit views for narrower contracts.
- Preserve existing router and explicit URL patterns.

## Data and authorization

- Use `select_related` for single-valued relationships and `prefetch_related` for collections when the response traverses them. Confirm query behavior rather than adding eager loads blindly.
- Apply authentication and operation or object permission to protected paths. A request-carried organization identifier is input, not proof of access.
- Keep transaction scope around the business operation that must succeed or fail together.

## Migrations and async

- Generate migrations through the project's command and inspect their real operations before delivery.
- Data migrations need a recovery path. Provide a reverse function when reversal is truthful and safe; do not fabricate a destructive or lossy reverse.
- Current Django supports async views and part of its ORM, while transactions still have async limitations. Check the installed version and keep sync-only work behind the documented sync boundary.

## Sources

- Django documentation — https://docs.djangoproject.com/
- Django async support — https://docs.djangoproject.com/en/stable/topics/async/
- Django REST Framework — https://www.django-rest-framework.org/
