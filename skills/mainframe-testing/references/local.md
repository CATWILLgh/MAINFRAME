# Lightweight local verification

Keep the default local loop short, deterministic and independent of external availability. Use existing runners and targeted selectors; inspect command side effects when unknown or changed. Reuse established evidence of what a command starts or changes. Measure slow setup or tests before claiming an optimization; do not impose a universal duration or test-count target.

| Risk | Default local proof | Additional CI proof when needed |
| --- | --- | --- |
| Calculations, validation, state transitions | Pure/in-process tests | Whole-suite regression and supported-version checks |
| HTTP or component contract | Real in-process handler/component with bounded collaborators | Actual browser, service and integration journeys |
| PostgreSQL constraints, SQL or transaction behavior | Isolated schema/database on verified disposable local PostgreSQL | Supported server versions, migrations, concurrency and upgrades beyond the local slice |
| Another engine, broker, object store or distributed protocol | Local orchestration/contract tests that state their limits | Correct engine/service, failure, delivery and persistence semantics |
| Layout/browser/device behavior | Existing lightweight component checks and assigned available preview observations | Browser journeys and platform coverage; mocks do not prove layout or device behavior |
| Deployment/topology/recovery | Scoped parsing, rendering and authorized dry-run | Relevant isolated environment and separately authorized runtime acceptance |

Broad suites, images, service stacks, real brokers, Redis, ClickHouse, Kubernetes, browsers requiring a full application stack, compatibility matrices and performance campaigns belong in CI by default. Do not install or launch them locally because a convenient test harness can. An explicit caller/project assignment can authorize a specific local exception; mere service availability or a generic development task is insufficient.

## PostgreSQL is an allowed option, not mandatory setup

Use PostgreSQL locally only when the changed behavior needs PostgreSQL semantics. Reuse an established local instance when available; installing or starting a server remains subject to process and infrastructure authority. Confirm server identity from actual local process/service ownership and connection routing. `localhost`, a port, client executable, container label or SSH tunnel does not establish a local server.

Under MAINFRAME's local PostgreSQL policy, a server verified to run entirely on this machine, without a tunnel/proxy/remote endpoint, can supply disposable databases or schemas for the assigned test work. Use uniquely named task-owned databases/schemas and bounded connections. Apply migrations to that target, use synthetic data, and clean up only the resources created or explicitly assigned for disposal. Do not reset unrelated databases merely because the server is local. This policy is not disposal authority for another engine or a remote/shared endpoint.

Transactions can isolate ordinary tests, but an automatic rollback fixture may hide commit behavior, separate-connection visibility, locks, migrations or after-commit effects. Use the faithful isolation boundary for those cases. Avoid parallel workers sharing schemas, ports, globals or uncontrolled pool budgets. Bound query/lock/statement timeouts and surface timeout causes rather than retrying until green.

## When local evidence is insufficient

Identify the actual behavior that requires another environment, the owning CI job/test and its trigger. Keep cheap local tests for what they can faithfully observe; never substitute SQLite/PostgreSQL for a different engine and claim compatibility. If the necessary CI job does not exist and changing CI is in scope, add it. If authority or infrastructure is unavailable, report that specific evidence gap; do not call the affected behavior verified.

Use `mainframe-infrastructure` for substantial runner/service provisioning and `mainframe-secrets` for credential delivery. Neither extends the task's authority. Browser acceptance and live operations remain distinct from test configuration or an unrun CI test.
