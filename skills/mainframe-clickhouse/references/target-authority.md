# Target and authority

Establish identity from the selected connection's configuration owner and actual
route, not from a label. Trace forwarded ports, proxies, container contexts, and
load balancers to their destinations. Cross-check project environment mapping,
service or cluster identity, and intended database. A bounded metadata query for
`version()`, `hostName()`, `currentUser()`, and `currentDatabase()` can corroborate
a permitted connection; none of these alone proves ownership or disposability.
Do not contact guessed endpoints to discover which one might be production.

Classify two dimensions separately: the server's operational impact and the
data's sensitivity. A local production-data copy may be operationally disposable
yet still contain protected records. Do not export, retain, or expose those
records merely because the server is a fixture.

## Match authority to the operation

- A diagnostic task permits relevant bounded observation, not arbitrary data
  export, long scans, load testing, configuration changes, or maintenance.
- A requested migration or correction may already authorize a specific write.
  Resolve its exact tables, predicates, dependencies, affected nodes, resource
  budget, and recovery method without demanding a second generic approval.
- A staging/test service remains shared unless ownership and disposal authority
  establish otherwise. Scope fixture names and teardown to owned resources;
  a shared database or server-wide setting is not a fixture.
- Unknown identity is not permission to experiment. Use production safeguards
  for any permitted identity read and withhold mutation until resolved.
- A request to reset "dev" does not authorize resetting a discovered production
  destination. Resolve that target mismatch with the caller before mutating;
  reuse authority only when it covers the actual target and operation.
- Reclassify when the connection, tunnel, role, database, cluster, storage, or
  task changes. Reuse current verified facts while that boundary remains valid.

## Effective access

For production diagnostics, prefer an existing dedicated least-privilege reader
with scoped grants and enforced resource constraints. Account provisioning is a
separate authorized change. `readonly=1` restricts statement classes; it is not
a complete authorization, data-isolation, egress, or resource policy. In current
documentation `readonly=2` allows more operations, including temporary tables and
`RESTORE`; `BACKUP` is not prevented by `readonly`. Verify version-specific
behavior, grants, profiles and constraints instead of trusting the name
"read-only" or an HTTP method.

Do not relax a profile or change `readonly` to make a query's `SETTINGS` pass.
Use permitted tighter limits or the existing enforced profile; if necessary
bounds cannot be established, narrow the query or return that exact limitation.
Never infer that a failed query authorizes escalation. Preserve TLS verification
and private access paths; do not open public ingress as a troubleshooting shortcut.

Reference: [Query permissions](https://clickhouse.com/docs/operations/settings/permissions-for-queries).
