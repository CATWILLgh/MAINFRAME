# Dokploy operations

Read this reference only after project evidence or the infrastructure map has
identified Dokploy as the target platform.

Resolve the instance through stable non-secret project metadata and the central
credential index. Current Dokploy API documentation uses an `x-api-key` header,
but verify authentication and endpoint behavior for the target version. Use
`mainframe-secrets` for value delivery and `mainframe-curl-requests` for bounded
HTTP mechanics.

## Discover the live contract

The target instance may expose its OpenAPI document through
`GET /api/settings.getOpenApiDocument`. Prefer extracting only the required
path, method, parameters, request schema, response schema, and error behavior
outside model context. Do not load a large authenticated specification or raw
environment response into the conversation.

Before every mutation not already verified during the active task:

1. Confirm the exact instance and its version.
2. Resolve the project, environment, resource, and stable identifiers through
   bounded reads.
3. Inspect the current endpoint schema from the instance or current official
   documentation.
4. Establish authority, blast radius, recovery, and observable completion.
5. Send one bounded request without exposing credentials.
6. Follow asynchronous work to a terminal state and re-read the resource.

Do not treat GET as universally harmless or POST as universally destructive.
Logs, environment responses, specifications, and resource metadata may contain
private data; endpoint semantics and active authority control the operation.

## Load the requested operation only

- Application source, build, configuration, and deployment:
  [applications.md](dokploy/applications.md)
- Docker Compose or Stack resources: [compose.md](dokploy/compose.md)
- Managed databases: [databases.md](dokploy/databases.md)
- Domains, ports, redirects, and TLS: [domains-tls.md](dokploy/domains-tls.md)
- Database, volume, platform backups, and rollback:
  [backups.md](dokploy/backups.md)
- Deployment, build, remote, or cluster servers: [servers.md](dokploy/servers.md)
- Any disruptive, destructive, access-changing, or recovery operation:
  [safety.md](dokploy/safety.md)

For an operation outside these guides, use the current API specification and
official documentation rather than inventing an endpoint or copying an old
payload.

Primary documentation:

- https://docs.dokploy.com/docs/api
- https://docs.dokploy.com/docs/core
