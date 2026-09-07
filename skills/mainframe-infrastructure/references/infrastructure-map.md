# Project infrastructure map

`.agents/infrastructure.json` is the shared, project-owned, non-secret map of
current environments. It reduces repeated discovery but never replaces live
checks or grants authority.

## Contract

- `schemaVersion` is `1`.
- `environments` is keyed by stable human-readable environment identifiers.
- Each entry records `purpose`, `platform`, `deployment`, `resources`,
  `credentialRefs`, `references`, `approvalRequired`, `lastVerified`, and
  optional short `notes`.
- `credentialRefs` contains names or native access aliases only. Never store
  values, password-bearing DSNs, keys, cookies, or authorization headers.
- Each reference has a short `purpose` and a repository-relative `path` that
  resolves inside the project and exists.
- Prefer stable aliases and platform resource identifiers over transient
  addresses. Store an address only when it is itself the durable identifier.
- `approvalRequired` highlights operations whose authority must be present in
  the active task. It neither grants authority nor requires asking twice when
  the task already supplies it.
- `lastVerified` is an ISO date or `null`. Update it only after every material
  fact in the environment entry has been verified.
- `notes` contains concise exceptional facts, not procedures or chronology.

Use the JSON asset as a structural starting point and replace every example
value. If an older MAINFRAME map already exists at this same path, preserve and
validate it instead of recreating it.

When reality and the map disagree, use reality for the active task. Repair the
map only when project edits are within scope; otherwise return the exact stale
fact. Keep long procedures in project runbooks and history in Git.
