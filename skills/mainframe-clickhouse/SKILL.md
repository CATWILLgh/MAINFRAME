---
name: mainframe-clickhouse
description: Plan, query, integrate, or troubleshoot ClickHouse, including query cost, ingestion, schema changes, deletion, and recovery across production, shared test, and disposable targets.
---

# Use ClickHouse within a verified boundary

Before connecting, resolve the endpoint, routing or tunnel, intended environment,
database/table, credential identity, and requested operation from applicable
project configuration and caller authority. A credential permits authentication;
it does not authorize an operation. Use `mainframe-infrastructure` for broader
deployment coordination and `mainframe-secrets` for credential delivery when
available. Do not print credentials or dump connection configuration.

Establish the boundary before executing SQL:

| Target | Operating boundary |
| --- | --- |
| Production | Scoped authorized reads with resource bounds; changes require authority for the exact operation and an adequate recovery boundary. |
| Shared staging/test | Preserve other users, persistent data, and shared capacity. Test naming does not authorize resets. |
| Verified disposable fixture | Create, change, or remove only the resources covered by explicit disposal authority; use representative tests without unnecessary production ceremony. |
| Unknown or conflicting identity | Do not write, reset, or run an expensive query. Resolve identity through configuration and the smallest permitted metadata read; continue offline work. |

Loopback addresses, local clients, containers, SSH tunnels, a database named
`test`, and a read-only account do not prove a disposable server. Verify the
actual destination and storage ownership. A separate test schema on a production
cluster still shares production resources. Reuse established authority; do not
ask again merely because the operation is sensitive. Do not invent ClickHouse
disposal permission from a policy covering another database.

## Read only the relevant method

| Current decision | Read |
| --- | --- |
| Target ambiguity, environment classification, or permission boundary | [Target and authority](references/target-authority.md) |
| SQL analysis, diagnostics, query correctness, or resource limits | [Safe queries](references/queries.md) |
| Ingestion, retries, schema, updates, deletes, or cluster-wide changes | [Writes and schema](references/writes.md) |
| Capacity, maintenance, incident cancellation, backup, or restore | [Operations and recovery](references/operations.md) |
| Version-sensitive syntax, settings, engine behavior, or missing details | [Official source map](references/sources.md), then applicable current documentation |

Use fully qualified targets and the established client. Inspect the actual
version, engine, effective settings, and topology only as needed for the task.
Do not transfer PostgreSQL transaction, uniqueness, or rollback assumptions to
ClickHouse. A read-only query can still overload a cluster or expose sensitive
data. A client success response may acknowledge queued work rather than its
completion.

Never bypass a denial by switching to an admin identity, disabling limits,
guessing another endpoint, or adding `ON CLUSTER`. Do not use table drops,
partition removal, forced merges, Keeper edits, or data-file deletion as generic
debugging. If an operation's outcome is uncertain, establish its status before
retrying or declaring failure. Stop only the blocked action and return the exact
missing fact or authority.

Complete the authorized result with proportionate evidence: identify the target,
scope, applied resource/recovery bounds, observed result, and material uncertainty.
Distinguish accepted work, local completion, replica/shard completion, reader
correctness, and physical removal when relevant. Do not claim production safety
from a local test or a successful health check.
