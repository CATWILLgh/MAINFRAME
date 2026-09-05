# Destructive-operation safety

Do not assume that a Dokploy resource deletion has dry-run or undo. Treat
`*.remove` and `*.delete` as irreversible unless the target instance's current
contract proves otherwise. Each call needs explicit authority for the exact
resource; authority already supplied by the active task is sufficient and must
not be requested again. The checks below prevent accidental widening.

Do not replace this target-aware check with a global permission pattern for
`curl`. A method or endpoint fragment cannot identify the Dokploy instance,
resource, existing authority, or current target schema, and would stop an
already authorized operation while remaining bypassable through another HTTP
client.

**Always safe (reads):** `*.one`, `*.all`, `*.readLogs`, `*.getServerMetrics`, `deployment.all`. Use these freely, and use `*.one` to confirm an ID resolves to the intended target **before** any destructive call.

## By blast radius

**1 — Self-lockout (can sever your own access):**
- `user.deleteApiKey` — may revoke the key you are authenticating with.
- `user.remove`, `sso.deleteProvider`, `sso.removeTrustedOrigin`.
- `gitProvider.remove`, `application.disconnectGitProvider`, `compose.disconnectGitProvider` — break future deploys of affected services.

**2 — Infrastructure / instance-wide (affects more than one app):**
- `server.remove`, `cluster.removeWorker` — remove a node from the cluster.
- `settings.reloadTraefik`, `settings.reloadServer`, `settings.reloadRedis` — restart shared infra; brief outage for everything behind it.
- `settings.cleanAllDeploymentQueue` — clears queued deployments across the instance.

**3 — Potential data loss or parent-resource cascade:**
- `project.remove` — **highest blast radius**: may remove or orphan every
  environment and resource below it; enumerate and verify the target version's
  behavior first.
- `environment.remove` — may affect every resource in that environment.
- `application.delete`, `compose.delete`.
- `postgres.remove` / `mysql.remove` / `mongo.remove` / `mariadb.remove` /
  `redis.remove` / `libsql.remove` — can remove managed data; verify storage and
  backup consequences from the target schema and current product behavior.
- `backup.remove`, `volumeBackups.delete`, `mounts.remove`, `destination.remove`, `registry.remove`, `certificates.remove`.

**4 — Running-service disruption (recoverable, but causes downtime / lost build state):**
- `application.stop` / `application.reload`; `compose.stop`; database `*.stop` / `*.reload` / `*.rebuild` (all six engines).
- `application.clearDeployments`, `application.cleanQueues`, `application.killBuild`, `application.cancelDeployment`, `application.dropDeployment` (and `compose.*` equivalents).
- `deployment.killProcess`, `deployment.removeDeployment`.

## Discipline

1. **Read before write.** Resolve and inspect the target with `*.one` first; verify the `name`/IDs match intent.
2. **No speculative destruction.** Do not fire class 1–3 calls without explicit
   authority for that exact resource. A child operation does not authorize its
   parent, sibling resources, or an instance-wide action.
3. **Mind the cascade.** Before `project.remove` or `environment.remove`,
   enumerate the children and verify the installed version's cascade behavior.
4. **`rebuild` ≠ `redeploy`.** `rebuild` discards build cache and can interrupt a running container; prefer `deploy`/`redeploy` for a routine update (see [deploy-application.md](deploy-application.md)).
5. **Do not treat deployment rollback as data recovery.** `rollback.*` concerns
   deployments, not deleted resources or database contents. Establish the
   separate recovery path first — see [backups.md](backups.md).
