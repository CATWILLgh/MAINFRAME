# Project infrastructure map

`.agents/infrastructure.json` is the current non-secret map of a project's
environments. It reduces repeated discovery; it never replaces live checks.

## Contract

- `schemaVersion` is currently `1`.
- `environments` is an object keyed by stable, human-readable environment ids.
- Each environment records `purpose`, `platform`, `deployment`, `resources`,
  `credentialRefs`, `references`, `approvalRequired`, `lastVerified`, and
  optional `notes`.
- `approvalRequired` names operations that must be explicitly included in the
  current task's authority rather than inferred from the map. Existing explicit
  authority satisfies the entry and is not requested again. An operation's
  absence from the list does not grant it or override the active task boundary.
- `credentialRefs` contains environment-variable names, credential-index names,
  or native access aliases only. Never store values, DSNs with passwords,
  private keys, session cookies, or authorization headers.
- A reference contains a short `purpose` and a repository-relative `path`.
  Paths must stay inside the project root and point to an existing file.
- Prefer access aliases and stable platform resource names over raw addresses.
  Store an address only when it is itself the durable operational identifier.
- `lastVerified` is an ISO date for the whole environment entry. Change it only
  after repository or live evidence confirms every material fact represented
  by that entry. A partial check may correct the affected fact but preserves
  the previous date; do not imply that untouched topology was reverified.
- `notes` holds short exceptional facts, not procedures or session history.

## Maintenance

Read only references relevant to the current operation. Update a fact after it
is observed, remove replaced facts instead of appending a chronology, and let
Git retain history. Keep long deploy, rollback, migration, recovery, or incident
procedures in referenced runbooks.

When verified reality and the map disagree, use reality for the active task.
Repair the map only when repository edits are within the task; otherwise
return the confirmed stale fact to the immediate caller. A stale map never
grants authority for an operation and never justifies guessing an environment.
