---
name: mainframe-go-backend
description: Design, implement, debug, or review Go services, APIs, and workers, including transactions, concurrency, retries, and backend tests.
---

# Go backend engineering

Apply this method whenever the active work matches the description, whether you
are the primary implementer, a delegated engineer, or a reviewer. Follow the
scope and authority supplied through the current execution path; this skill does
not expand either.

## Establish the active service boundary

Identify the Go module and package that own the behavior. Trace the real process
entrypoint through registration, middleware or worker wiring, business rules,
persistence and external boundaries, side effects, callers, and observable
output. A package name, interface, or passing unit test alone does not prove the
active runtime path.

Several modules, commands, routers, database clients, generated packages, and
test styles may legitimately coexist. Resolve ownership from `go.mod`,
`go.work`, imports, constructors, registration, process commands, build tags,
configuration, and affected tests. Read [reconnaissance](references/recon.md)
when ownership or runtime wiring is unclear.

## Preserve the established system

Preserve the supported Go and toolchain versions, module/workspace layout,
router, persistence library, error contract, concurrency model, observability,
deployment boundary, and verification conventions unless changing one is part
of the assigned result. Do not introduce another router, ORM, migration tool,
worker system, or abstraction layer for convenience.

Keep non-trivial business behavior independent of transport when the established
architecture supports that separation. Pass `context.Context` through request,
database, provider, and background boundaries; derive bounded child contexts at
the operation that owns the deadline. Treat goroutines, transactions,
connections, response bodies, timers, and channels as owned resources with a
defined completion and cleanup path.

Verify installed or selected versions before relying on version-sensitive
behavior. Prefer the owning project's source and current primary documentation.

## Load only the relevant detail

| Changed concern | Read |
|---|---|
| Module, workspace, commands, build tags, generated ownership, or toolchain | [runtime and packaging](references/runtime-and-packaging.md) |
| HTTP, middleware, request/response contracts, sessions, authentication, or authorization | [HTTP and security](references/http-and-security.md) |
| Queries, transactions, locks, pool pressure, migrations, or concurrent state transitions | [data and concurrency](references/data-and-concurrency.md) |
| Outbound APIs, retries, rate limits, idempotency, or ambiguous external writes | [integrations and resilience](references/integrations-and-resilience.md) |
| Goroutines, workers, schedulers, synchronization, pagination checkpoints, or realtime delivery | [background and lifecycle](references/background-and-lifecycle.md) |
| Choosing focused Go evidence, race checks, or a real dependency boundary | [testing](references/testing.md) |

## Complete and verify the assigned result

Make the smallest complete change across every affected location inside the
assigned boundary. Validate untrusted data at the real boundary, authorize the
concrete action and resource server-side, preserve causal errors, and make
atomicity, lock order, compare-and-set behavior, idempotency, retry termination,
and side-effect timing explicit wherever correctness depends on them.

Use the project's native commands and the smallest faithful evidence for the
changed risk. Run focused tests first, then the nearest relevant fast package
checks. Use `-race`, the real database engine, a real process boundary, or a
provider call only when that behavior is the risk and current instructions and
authority permit it. Keep local simulation, live read compatibility, and real
external mutation as separate evidence levels.

Do not replace completion with TODOs, weakened validation or assertions,
unbounded retries, swallowed errors, leaked goroutines, compatibility debris,
or an unrecorded follow-up. Keep credentials and sensitive payloads out of
source, logs, errors, fixtures, and serialized output. Preserve unrelated work.
When a concrete out-of-scope project problem remains, record or reconcile it
through the available project problem route when authorized, then return to the
assigned result without expanding the investigation.
