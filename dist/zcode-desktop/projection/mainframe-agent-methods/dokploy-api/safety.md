# Destructive-operation safety

The Dokploy API has **no dry-run and no undo** for resource deletion. `*.remove` / `*.delete` take effect immediately and irreversibly. Default to read-only; treat every call below as requiring explicit authorization before firing — especially in autonomous runs. (The official MCP server's issue #46 — *"my agent deleted my entire Dokploy app"* — is exactly this failure mode; discipline here is the mitigation.)

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

**3 — Data loss (irreversible, cascades):**
- `project.remove` — **highest blast radius**: cascades to every environment, application, compose and database under it.
- `environment.remove` — cascades to all resources in that environment.
- `application.delete`, `compose.delete`.
- `postgres.remove` / `mysql.remove` / `mongo.remove` / `mariadb.remove` / `redis.remove` / `libsql.remove` — destroys the database and its volume.
- `backup.remove`, `volumeBackups.delete`, `mounts.remove`, `destination.remove`, `registry.remove`, `certificates.remove`.

**4 — Running-service disruption (recoverable, but causes downtime / lost build state):**
- `application.stop` / `application.reload`; `compose.stop`; database `*.stop` / `*.reload` / `*.rebuild` (all six engines).
- `application.clearDeployments`, `application.cleanQueues`, `application.killBuild`, `application.cancelDeployment`, `application.dropDeployment` (and `compose.*` equivalents).
- `deployment.killProcess`, `deployment.removeDeployment`.

## Discipline

1. **Read before write.** Resolve and inspect the target with `*.one` first; verify the `name`/IDs match intent.
2. **No speculative destruction.** In autonomous/auto-mode, do not fire class 1–3 calls without prior explicit authorization for that specific resource.
3. **Mind the cascade.** `project.remove` and `environment.remove` delete children silently — enumerate what is under them (`*.all` filtered by the id) before removing.
4. **`rebuild` ≠ `redeploy`.** `rebuild` discards build cache and can interrupt a running container; prefer `deploy`/`redeploy` for a routine update (see [deploy-application.md](deploy-application.md)).
5. **Deletion has no rollback.** `rollback.*` exists for *deployments*, not for deleted resources or databases. Back up first — see [backups.md](backups.md).
