---
name: dokploy-api
description: "Operate a Dokploy instance through its HTTP API (self-hosted PaaS on Docker + Traefik): authentication via the `x-api-key` header, the tRPC-over-OpenAPI call convention (GET = flat query params, POST = JSON body, bare-JSON responses, `{message,code,issues}` errors), the resource hierarchy Project -> Environment -> {Application | Compose | Database}, and canonical workflows for deploying applications and Compose stacks, provisioning databases, attaching domains/TLS, and managing servers and backups. Includes destructive-operation safety and a live-spec navigation technique for any endpoint beyond the cookbook."
when_to_use: "Use when interacting with a Dokploy server: creating projects or environments, deploying or redeploying an application or Docker Compose stack, provisioning a database (Postgres/MySQL/MongoDB/Redis/MariaDB/LibSQL), attaching a domain or issuing Let's Encrypt certificates, reading deployment logs or status, managing servers or backups, or calling any tRPC-style `*.create` / `*.deploy` / `*.one` endpoint with an `x-api-key`. Also applies when a project's config references a Dokploy instance, `DOKPLOY_URL`, or a `DOKPLOY_API_KEY`."
user-invocable: false
---

# Working with the Dokploy API

Dokploy is a self-hostable PaaS (Docker + Traefik) — a Heroku/Vercel/Netlify alternative. This skill drives a running instance through its HTTP API.

**Config is never hardcoded.** The base URL and API key belong to the target project/environment, not to this skill. Read them from project config or the environment (`DOKPLOY_URL`, `DOKPLOY_API_KEY`); see [`secrets-handling`](../secrets-handling/SKILL.md). Never inline the key into a command shown to the user or into logs.

## Authentication & base URL

- **Base URL:** `<DOKPLOY_URL>/api` — every endpoint lives under the `/api` prefix.
- **Auth header:** `x-api-key: <key>`.

> Spec caveat: every endpoint's `security` requirement is labelled `Authorization`, but the only scheme actually defined in the OpenAPI (`components.securitySchemes`) is an API key in the `x-api-key` header. The label is a known `trpc-to-openapi` generator artifact — **send `x-api-key`**, not an `Authorization` header. A missing/invalid key returns `401` with body `{"message":"Authorization not provided", ...}`.

Generate the key in the Dokploy dashboard (user/profile → API keys); it maps to `user.*` API-key endpoints. Store it in the project's secret source, load via env.

## Call convention (tRPC-over-OpenAPI)

The API is tRPC exposed as OpenAPI. Paths are RPC-style `/<resource>.<action>`, not REST resources.

- **GET = query.** Parameters are **flat query params** (e.g. `?applicationId=abc`), not a JSON `?input=` wrapper. Read actions: `*.one`, `*.all`, `*.readLogs`, `*.getServerMetrics`.
- **POST = mutation.** Body is **bare JSON** matching the endpoint's `requestBody` schema. Write actions: `*.create`, `*.update`, `*.save*`, `*.deploy`, `*.remove`.
- **Responses are bare JSON** per each endpoint's own schema — there is **no** `{result:{data:{json}}}` wrapper (that envelope only appears at the raw tRPC layer, not on these OpenAPI endpoints).
- **Errors:** HTTP `400` `BAD_REQUEST`, `401` `UNAUTHORIZED`, `403` `FORBIDDEN`, `404` `NOT_FOUND`, `500` `INTERNAL_SERVER_ERROR`, each with body `{"message": string, "code": string, "issues"?: [{"message": string}]}`. Always gate on the status code with `--fail-with-body` so failures surface (see [`curl-requests`](../curl-requests/SKILL.md)).

```bash
# GET (query): read one application
curl -sS --fail-with-body -G \
  -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "applicationId=$APP_ID" \
  "$DOKPLOY_URL/api/application.one"

# POST (mutation): create a project
curl -sS --fail-with-body -X POST \
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

Resolve or create the `environmentId` **before** creating an Application/Compose/Database. (In Dokploy ≥ v0.29 the `environment` layer is mandatory; older versions attached apps directly to projects — do not assume the old shape.)

## Discover existing resources

Operating an existing instance starts with finding IDs. These reads return the resource tree:

```bash
curl -sS --fail-with-body -H "x-api-key: $DOKPLOY_API_KEY" "$DOKPLOY_URL/api/project.all"            # all projects (no params)
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "projectId=<id>" "$DOKPLOY_URL/api/project.one"                                     # one project + its environments/resources
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "projectId=<id>" "$DOKPLOY_URL/api/environment.byProjectId"                         # environments under a project
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "name=web" "$DOKPLOY_URL/api/application.search"                                    # find apps (also q/appName/owner/repository)
```

Create endpoints return the new resource — read its id (e.g. `projectId`) to chain the next call. If a create returns an empty body, resolve the id with these reads (match by `name`). Capture the id you need **before** any update / deploy / destructive call.

## Safety first

~80 endpoints are destructive (delete, data-loss, infra-level, deploy-disruption, self-lockout). Default to read-only; confirm before any destructive call, especially in autonomous runs. **Before any `*.remove` / `*.delete` / `*.destroy` / `server.remove` / `*.reload` — read [`safety.md`](safety.md).**

## Live-spec navigation (the long tail)

The instance serves its own full OpenAPI (529 endpoints) at `GET /api/settings.getOpenApiDocument`. It is ~850 KB of single-line JSON — never load it whole. Extract one endpoint's schema with `jq`:

```bash
curl -sS --fail-with-body -H "x-api-key: $DOKPLOY_API_KEY" \
  "$DOKPLOY_URL/api/settings.getOpenApiDocument" \
  | jq '(.result.data.json // .).paths["/postgres.create"]'   # one endpoint's schema
# Body may be bare {openapi,...} or tRPC-wrapped {result:{data:{json:...}}};
# the (.result.data.json // .) prefix handles both. Discover a domain's endpoints:
#   ... | jq -r '(.result.data.json // .).paths | keys[] | select(startswith("/backup."))'
```

Use this for any endpoint not covered by the cookbook below.

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
| Any other domain (43 total) — find the right tag | [endpoint-map.md](endpoint-map.md) |

## Cross-references

- [`curl-requests`](../curl-requests/SKILL.md) — HTTP mechanics: `--fail-with-body`, timeouts, never inlining secrets.
- [`secrets-handling`](../secrets-handling/SKILL.md) — where `DOKPLOY_API_KEY` lives and how to substitute it without leaking the value.
- [`surface-ticket`](../surface-ticket/SKILL.md) — defer an out-of-scope Dokploy fix instead of silently working around it.
