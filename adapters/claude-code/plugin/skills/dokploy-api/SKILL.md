---
name: dokploy-api
description: "Internal Dokploy branch for the model-invocable `infrastructure` skill: HTTP API mechanics, resource hierarchy, deployment and Compose workflows, databases, domains/TLS, servers, backups, destructive-operation safety, and live-spec navigation."
when_to_use: "A Dokploy operation is already in flight through the `infrastructure` skill. Read directly from that skill's routing instructions; this branch is not independently model-invocable."
user-invocable: false
disable-model-invocation: true
---

# Working with the Dokploy API

This is the hidden Dokploy branch of `mainframe:infrastructure`. The primary
session reads it through that skill when the project map or verified recon
identifies Dokploy.

Dokploy is a self-hostable PaaS built on Docker and Traefik. This skill drives a
resolved running instance through its HTTP API.

**Config is never hardcoded.** Resolve the non-secret base URL from the project
infrastructure map or verified project configuration. Resolve the API-key name
and its approved access pattern only through
[`secrets-handling`](../secrets-handling/SKILL.md) and the credentials index.
An already-exported `DOKPLOY_API_KEY` is valid only when that index names it.
Never read arbitrary config in search of a key or expose the value in output.

## Authentication & base URL

- **Base URL:** `<DOKPLOY_URL>/api` — every endpoint lives under the `/api` prefix.
- **Auth header:** `x-api-key: <key>`.

The current official API reference defines API-key authentication in the
`x-api-key` header. Do not substitute an `Authorization` header merely because
an UI label says “Authorization”.

Creating, rotating, or deleting an API key is credential-store administration
and requires explicit authority outside this operational branch.

## Call convention (tRPC-over-OpenAPI)

The API is tRPC exposed as OpenAPI. Paths are RPC-style `/<resource>.<action>`, not REST resources.

- **GET = query.** Parameters are **flat query params** (e.g. `?applicationId=abc`), not a JSON `?input=` wrapper. Read actions: `*.one`, `*.all`, `*.readLogs`, `*.getServerMetrics`.
- **POST = mutation.** Body is **bare JSON** matching the endpoint's `requestBody` schema. Write actions: `*.create`, `*.update`, `*.save*`, `*.deploy`, `*.remove`.
- **Responses are bare JSON** per each endpoint's own schema — there is no `{result:{data:{json}}}` wrapper (that envelope only appears at the raw tRPC layer, not on these OpenAPI endpoints).
- **Errors:** gate on the HTTP status with `--fail-with-body`; common current
  responses use `400`, `401`, `403`, `404`, and `500` with `code`, `message`,
  and sometimes `issues`. Verify the exact endpoint contract instead of
  assuming every action exposes every status.

```bash
# GET (query): read one application
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G \
  -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "applicationId=$APP_ID" \
  "$DOKPLOY_URL/api/application.one"

# POST (mutation): create a project
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 \
  -H "x-api-key: $DOKPLOY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-project"}' \
  "$DOKPLOY_URL/api/project.create"
```

## Resource hierarchy

A deployable resource is never created in isolation — it hangs off an environment, which hangs off a project:

```
Project            (required: name)
  └─ Environment   (required: name, projectId)
       ├─ Application   (required: name, environmentId)
       ├─ Compose       (required: name, environmentId)
       └─ Database      (required: name, environmentId, + db credentials)
```

Resolve or create the `environmentId` before creating an
Application/Compose/Database. If an older installed instance exposes a
different schema, its own OpenAPI document controls that instance.

## Discover existing resources

Operating an existing instance starts with finding IDs. These reads return the resource tree:

```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" "$DOKPLOY_URL/api/project.all"            # all projects (no params)
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "projectId=<id>" "$DOKPLOY_URL/api/project.one"                                     # one project + its environments/resources
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "projectId=<id>" "$DOKPLOY_URL/api/environment.byProjectId"                         # environments under a project
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "name=web" "$DOKPLOY_URL/api/application.search"                                    # find apps (also q/appName/owner/repository)
```

Create endpoints return the new resource — read its id (e.g. `projectId`) to chain the next call. If a create returns an empty body, resolve the id with these reads (match by `name`). Capture the id you need before any update / deploy / destructive call.

## Safety first

Default to reads until the active task explicitly authorizes a mutation. Do not
ask again for an exact operation already authorized, but never widen that
authority to a sibling resource, parent environment, project, or instance-wide
action. Before any removal, deletion, reload, or similarly disruptive action,
read [`safety.md`](safety.md).

## Live-spec navigation (the long tail)

The instance serves its own version-specific OpenAPI document at
`GET /api/settings.getOpenApiDocument`. It can be large, so do not load it into
model context whole. Extract only the required endpoint or tag with `jq`:

```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" \
  "$DOKPLOY_URL/api/settings.getOpenApiDocument" \
  | jq '(.result.data.json // .).paths["/postgres.create"]'   # one endpoint's schema
# Body may be bare {openapi,...} or tRPC-wrapped {result:{data:{json:...}}};
# the (.result.data.json // .) prefix handles both. Discover a domain's endpoints:
#   ... | jq -r '(.result.data.json // .).paths | keys[] | select(startswith("/backup."))'
```

Use this before every mutation whose schema has not already been verified
against the target instance during the active task. The cookbook is operational
guidance, not a frozen replacement for the installed instance's contract.

## Cookbook (open only what the task needs)

| Task | File |
|---|---|
| Deploy an application from Git or a Docker image | [deploy-application.md](deploy-application.md) |
| Deploy a Docker Compose stack | [deploy-compose.md](deploy-compose.md) |
| Provision a database and connect it to an app | [databases.md](databases.md) |
| Attach domains, issue TLS, redirects, ports | [domains-tls.md](domains-tls.md) |
| Manage servers / multi-node / Docker on a node | [servers.md](servers.md) |
| Database & volume backups | [backups.md](backups.md) |
| Destructive-operation safety (read first) | [safety.md](safety.md) |
| Any other domain — find the right tag | [endpoint-map.md](endpoint-map.md) |

## Cross-references

- [`curl-requests`](../curl-requests/SKILL.md) — HTTP mechanics: `--fail-with-body`, timeouts, never inlining secrets.
- [`secrets-handling`](../secrets-handling/SKILL.md) — where `DOKPLOY_API_KEY` lives and how to substitute it without leaking the value.
- [`ticket`](../ticket/SKILL.md) — defer an out-of-scope Dokploy fix instead of silently working around it.

## Sources

- [Dokploy API](https://docs.dokploy.com/docs/api) — authentication, RPC-style paths, and the current API reference.
- [Application API](https://docs.dokploy.com/docs/api/reference-application) and [Compose API](https://docs.dokploy.com/docs/api/reference-compose) — deployment resource contracts.
- [Environment API](https://docs.dokploy.com/docs/api/reference-environment) and [Project API](https://docs.dokploy.com/docs/api/reference-project) — resource hierarchy.
- [Domain API](https://docs.dokploy.com/docs/api/reference-domain) and [Postgres API](https://docs.dokploy.com/docs/api/reference-postgres) — ingress and managed-database contracts.
- [Backup API](https://docs.dokploy.com/docs/api/reference-backup) — scheduled and manual backup actions.
- [Server API](https://docs.dokploy.com/docs/api/reference-server) and [remote servers](https://docs.dokploy.com/docs/core/remote-servers) — server actions and current product limitations.
