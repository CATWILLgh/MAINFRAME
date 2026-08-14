# Managed databases

Dokploy manages six database engines, each with the same lifecycle and endpoint shape — swap the tag prefix:

| Engine | Tag prefix |
|---|---|
| PostgreSQL | `postgres.*` |
| MySQL | `mysql.*` |
| MariaDB | `mariadb.*` |
| MongoDB | `mongo.*` |
| Redis | `redis.*` |
| LibSQL | `libsql.*` |

A database lives under an environment. Use the resolved URL and credential
access from [SKILL.md](../dokploy.md), resolve the `environmentId`, and verify the
chosen engine's create schema against the target instance.

## 1. Create & deploy

```bash
# Postgres: name/databaseName/databaseUser/databasePassword/environmentId required; dockerImage defaults to postgres:18
# Feed the registered password directly into jq and then curl; it never enters
# model output or a command argument.
secret get REGISTERED_DB_PASSWORD | jq -Rs --arg environmentId "<environmentId>" '{
  name:"acme-db", databaseName:"acme", databaseUser:"acme",
  databasePassword:rtrimstr("\n"), environmentId:$environmentId
}' | curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 \
  -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" \
  --data-binary @- "$DOKPLOY_URL/api/postgres.create"
# provision the container (async)
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 \
  -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" \
  -d '{"postgresId":"<id>"}' "$DOKPLOY_URL/api/postgres.deploy"
```

Required credential fields differ per engine (Redis has no `databaseName`/`databaseUser`, etc.) — pull the exact schema with the live-spec `jq` technique before calling.

## 2. Connect an application

A database and an app in the same project/environment share the Dokploy internal Docker network. Connect by the database's **internal host** (its generated service name), not a public address:

1. `GET /api/postgres.one?postgresId=<id>` — read the generated connection details (host, port, internal URL).
2. Set the app's connection string via `application.saveEnvironment` (e.g. `DATABASE_URL=postgresql://acme:<pw>@<internal-host>:5432/acme`) — see [deploy-application.md](deploy-application.md).

Expose a database publicly only when required (an external port) — prefer internal-only access.

## 3. Operate

- **Logs:** `GET /api/postgres.readLogs?postgresId=<id>`.
- **Lifecycle:** `postgres.reload`, `postgres.rebuild`, `postgres.stop` — disrupt the running DB; see [safety.md](safety.md).
- **Backups:** schedule and run via [backups.md](backups.md) before any destructive change.
- Treat `postgres.remove` and the equivalent engine operations as potential
  data loss. Verify the target version's deletion semantics and establish a
  tested recovery path before an authorized removal.
