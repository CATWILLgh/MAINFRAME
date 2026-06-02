# Django + DRF patterns

Batteries-included sync-first framework. ORM: Django ORM (built-in). API layer: Django REST Framework. Validation: DRF serializers → also [validation.md](validation.md).

## Apps + project structure

- One Django app per bounded context (`apps/jobs/`, `apps/users/`, `apps/billing/`).
- `models.py` for ORM models, `serializers.py` for DRF, `views.py` or `viewsets.py` for endpoints, `urls.py` for routing.
- Business logic in a `services.py` per app — keep ViewSets thin, models don't carry orchestration.

## DRF ViewSets + routers

- `ModelViewSet` for full CRUD; mix-in specific generics (`ListAPIView`, `CreateAPIView`) for partial surface.
- `DefaultRouter` auto-generates URL patterns; explicit `path()` only for non-RESTful actions.
- `@action(detail=True, methods=["post"])` for state-transition endpoints (e.g. `/jobs/{id}/complete/`).

```python
class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.select_related("machine").prefetch_related("downtimes")
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, HasRole]
```

## Eager loading — Django equivalents

- `select_related(...)` — many-to-one / one-to-one (JOIN, single query). Mirror of SA `joinedload`.
- `prefetch_related(...)` — one-to-many / many-to-many (separate query, IN-clause). Mirror of SA `selectinload`.
- Anti-pattern: chained `.objects.get(...).related.all()` loops → N+1. Define a manager method that pre-fetches.

## Permissions + authentication

- DRF `permission_classes` per ViewSet OR a global default in `REST_FRAMEWORK` settings.
- Custom `permissions.BasePermission` for role + tenant checks. `request.user.organization_id` is the truth, not request body.
- `IsAuthenticated` is the floor on protected endpoints — never `AllowAny` by default.

## Migrations

- One migration per logical change, generated via `python manage.py makemigrations`.
- Always inspect the generated file before committing — Django sometimes generates redundant operations.
- Data migrations: use `RunPython` with both `forward` and `reverse` functions; never irreversible by default.
- **Zero-downtime safety — `AddIndexConcurrently` + `atomic = False`, expand-contract, batched backfills: see [migrations.md](migrations.md).**

## Async caveat

Django ≥ 4.1 supports async views and async ORM (`await Model.objects.aget(...)`). Mature for read-heavy use; for write-heavy multi-step business logic, sync remains less risky in 2026.

## Sources

- Django docs — https://docs.djangoproject.com/
- DRF docs — https://www.django-rest-framework.org/
