# Data, state, and forms

Preserve the active data and state mechanisms. Framework-native fetching, a project client, TanStack Query, SWR, Apollo, Redux, Zustand, local state, and URL state are valid in different projects. Do not add a cache or global store for one local need.

Give each fact one owner. Avoid copying remote snapshots into another global store; an optimistic value or form draft may diverge only with an explicit reconciliation path. Include every parameter that changes a result in its cache identity without leaking state across users or tenants.

Define cancellation, retry, pagination, invalidation, freshness, optimistic rollback, and conflict behavior from the product contract. Never show durable success before the authoritative operation succeeds.

Use native controls and the simplest established form model that faithfully covers the interaction. Keep visible labels, programmatic descriptions and errors, keyboard submission, duplicate-submission prevention, server field-error reconciliation, and preservation of entered values after recoverable failure.

Client validation improves feedback; protected rules and durable state remain server-owned. Types and assertions do not validate uncertain runtime data. Reuse the project's validator when the boundary needs one instead of adding a competing schema library.
