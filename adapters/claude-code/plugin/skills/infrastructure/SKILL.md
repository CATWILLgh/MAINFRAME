---
name: infrastructure
user-invocable: false
description: "Operate and maintain a project's deployment and infrastructure from the primary session: environment topology, Docker and Compose, CI/CD, Dokploy, domains and TLS, observability, and the operational layer of PostgreSQL or Redis. Uses a project-owned infrastructure map and verifies live state before consequential actions."
when_to_use: "An active task changes, deploys, diagnoses, or verifies infrastructure: Dockerfile or Compose work, CI/CD configuration, deployment or rollback, environment selection, domains/TLS, remote service health, logs, backups, managed databases, PostgreSQL operations, Redis persistence, or credentials consumed by those operations. Not for ordinary application or UI implementation."
---

# Infrastructure operations

The primary session is the intended owner of this skill. Infrastructure work
commonly crosses environment choice, credentials, downtime, data, and granted
authority; do not delegate the whole operation merely to obtain specialist
context. A recipient that does not own those decisions returns verified facts
and the exact missing decision to its immediate caller instead of acting or
addressing the end user.

## Start with the project map

1. Resolve the project root from the active repository, falling back to the
   current working directory only when there is no repository.
2. If `<project-root>/.agents/infrastructure.json` exists, read it before
   infrastructure recon or action. It is the current topology map, not a log
   and not authority to mutate a resource.
3. Select the environment named or implied by the agreed task. If two map
   entries remain plausible and choosing one changes infrastructure or data,
   resolve that ambiguity before acting.
4. Read only the map's `references` whose `purpose` applies to the current
   operation. Resolve relative paths from the project root. A missing or
   escaping path is stale data, not permission to guess.
5. Treat `credentialRefs` as names only. Load `mainframe:secrets-handling`
   before consuming credentials; never place values in the map, commands shown
   in chat, logs, or generated runbooks.

Read [infrastructure-map.md](infrastructure-map.md) before creating or changing
the map. Use [infrastructure.example.json](infrastructure.example.json) as its
shape; do not copy example values as project facts.

## Establish current reality

The map is orientation, while the repository and live platform establish the
current state. Inspect the relevant Dockerfile, Compose, CI, IaC, deployment,
and environment-template files. For a remote operation, use the mapped access
alias and perform the smallest read-only live check that distinguishes current
state from stale documentation.

When the map conflicts with verified reality, reality wins. Correct the map
after the relevant fact is established. Do not update `lastVerified` for an
environment merely because its JSON entry was read.

Use current primary documentation or Context7 for version-sensitive platform,
CLI, configuration, or database behaviour. Project files and reproducible live
observations remain authoritative for project-local facts.

## Load only the applicable branch

- Dockerfile, image, or Compose work: read [containers.md](containers.md).
- PostgreSQL or Redis operational work: read [data-stores.md](data-stores.md).
- Any infrastructure change or diagnosis: read
  [verification.md](verification.md) before declaring the result complete.
- Dokploy: read the internal [Dokploy API guide](../dokploy-api/SKILL.md), then
  only its cookbook file for the requested operation. Read its `safety.md`
  before a destructive or disruptive endpoint.
- Starting, stopping, or restarting a local process or Compose stack: load
  `mainframe:ops-app-server-safety` first.
- Raw HTTP interaction: load `mainframe:curl-requests`.

Do not preload every branch. CI/CD systems and other platforms are derived from
the repository's actual provider files and current official documentation,
not from a universal vendor-neutral recipe.

## Change safely

- Confirm the exact target before any remote write. A production-looking name
  is not enough when the map contains several contours.
- Do not proceed without the required decision for a new or changed
  infrastructure choice, downtime, destructive operation, irreversible data
  change, permission expansion, or operation outside the already agreed target.
  A recipient that cannot obtain that decision directly returns it to its
  immediate caller.
- Prefer reversible and idempotent changes. Establish the rollback mechanism
  before applying a change whose failure can interrupt service or data access.
- Do not widen credentials or permissions to make a command pass.
- Never infer success from exit code alone. Observe the changed resource and
  the product-facing effect appropriate to the operation.

## Maintain durable project context

After a verified infrastructure change, update the affected map entry and its
`lastVerified` date in the same authorized repository change. Add a runbook
reference when the procedure cannot be represented as a concise fact; keep the
procedure in the referenced project file rather than embedding commands or
long prose in JSON.

If the map is absent and the task establishes durable infrastructure facts,
create it when repository edits are in scope. During read-only diagnosis,
return the confirmed missing map content to the caller instead of mutating the
repository. Git holds history; do not create JSONL history or duplicate stale
environment records.
