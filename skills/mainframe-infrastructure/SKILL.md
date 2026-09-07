---
name: mainframe-infrastructure
description: Diagnose, change, and verify project infrastructure across environments, containers, CI/CD, domains, TLS, observability, backups, operational data stores, and Dokploy. Use for infrastructure-owned work, not ordinary application or UI implementation.
---

# Infrastructure work

Operate only within the target and authority established by the current task.
This skill does not grant permission to deploy, restart, delete, change data,
expand access, or contact an unrelated environment.

## Establish the target

1. Resolve the project root from version control, using the working directory
   only when no repository exists.
2. If `.agents/infrastructure.json` exists, read it as a non-secret orientation
   map. It is neither live state nor authority.
3. Resolve the exact environment, platform instance, and resource. Stop on an
   ambiguity that could affect infrastructure or data.
4. Read only project references applicable to the requested operation. Reject
   stale, missing, or project-escaping reference paths instead of guessing.
5. Resolve credential names through the central MAINFRAME credential index and
   use `mainframe-secrets` for value delivery.

Read [infrastructure-map.md](references/infrastructure-map.md) before creating
or changing the map. Use
[infrastructure.example.json](assets/infrastructure.example.json) as a shape,
never as evidence about a real project.

## Establish current reality

The map provides orientation. Repository configuration and bounded live
observations establish current state. Inspect the applicable Dockerfile,
Compose, IaC, CI/CD, environment template, deployment, and runbook files. For a
remote task, perform only the smallest authorized read that distinguishes live
state from stale documentation.

When verified reality conflicts with the map, reality controls the active task.
Repair the map only when repository edits are in scope. Never refresh a
verification date merely because a file was read.

Use current primary documentation for version-sensitive platform, CLI,
configuration, database, and API behavior.

## Load only the applicable branch

- Dockerfile, image, container runtime, or Compose work: read
  [containers.md](references/containers.md).
- Operational PostgreSQL, Redis, backup, restore, replication, or failover
  work: read [data-stores.md](references/data-stores.md).
- Dokploy: read [dokploy.md](references/dokploy.md), then only the operation
  reference it selects.
- Any infrastructure diagnosis or change: read
  [verification.md](references/verification.md) before declaring completion.
- Raw HTTP calls must follow `mainframe-curl-requests`.

Do not preload every branch or substitute a generic recipe for the project's
actual provider and version.

## Change safely

- Confirm the exact instance, environment, and resource before a remote write.
- Establish the actual blast radius, data and downtime implications, required
  access, rollback or recovery path, and observable success condition.
- Check that the current task authorizes that exact operation. A map entry,
  credential, read permission, HTTP method, or available tool never grants
  authority by itself.
- Do not repeat an approval already supplied for the same bounded operation,
  but do not widen it to parent, sibling, or instance-wide resources.
- Prefer reversible and idempotent changes. Do not widen permissions or weaken
  security checks merely to make an operation pass.
- Apply the smallest adequate change, then re-read the affected resource and
  verify the product-facing contract.

## Maintain durable context

After a verified change, update only the affected map facts when project edits
are within scope. Change `lastVerified` only after every material fact in that
environment entry has been checked. A partial check may correct one fact but
must preserve the previous date. Keep procedures in referenced project
runbooks and let Git retain history.

If durable facts were established but project edits are outside the task,
return the exact proposed map update without writing it.
