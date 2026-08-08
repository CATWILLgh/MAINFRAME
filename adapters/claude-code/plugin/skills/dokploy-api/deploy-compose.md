# Deploy a Docker Compose stack

A Compose stack is one Dokploy resource (`compose`) wrapping a multi-service `docker-compose.yml`. Like applications it lives under an environment and deploys asynchronously. Prereqs: `$DOKPLOY_URL`, `$DOKPLOY_API_KEY`, and the hierarchy in [SKILL.md](SKILL.md#resource-hierarchy).

```bash
H=(-H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json")
```

## 1. Create the compose resource

`composeType` is `docker-compose` (single host) or `stack` (Docker Swarm). You can pass the YAML inline as `composeFile`, or leave it empty and attach a Git source in step 2.

```bash
curl -sS --fail-with-body "${H[@]}" -d '{
  "name":"analytics","environmentId":"<environmentId>","composeType":"docker-compose",
  "composeFile":"services:\n  web:\n    image: nginx:1.27\n    ports:\n      - 8080:80"}' \
  "$DOKPLOY_URL/api/compose.create"   # -> capture composeId
```

## 2. Source: inline vs Git (pick ONE)

- **Inline:** the `composeFile` above is enough.
- **From Git:** compose has no `save*Provider` endpoints — set the source on the compose entity with `compose.update` (sourceType + repository/branch/provider fields; `compose.fetchSourceType` inspects it). Pull the exact field set via the live-spec `jq` technique.

## 3. Env, deploy, logs

```bash
# stack-level env (interpolated into ${VARS} in the compose file)
curl -sS --fail-with-body "${H[@]}" -d '{"composeId":"<id>","env":"POSTGRES_PASSWORD=secret"}' \
  "$DOKPLOY_URL/api/compose.saveEnvironment"
# deploy (async, returns {})
curl -sS --fail-with-body "${H[@]}" -d '{"composeId":"<id>"}' "$DOKPLOY_URL/api/compose.deploy"
# logs — compose.readLogs needs the target container too (a stack has several)
# list services/containers first: GET /api/compose.loadServices?composeId=<id>
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "composeId=<id>" --data-urlencode "containerId=<containerId>" \
  "$DOKPLOY_URL/api/compose.readLogs"
```

## Internal networking

Services in the same stack reach each other by **service name as host** on the shared Docker network — no published port needed. Per Dokploy's official templates, e.g. `DATABASE_URL: postgresql://user:pass@postgres:5432/db` where `postgres` is the service name (source: docs.dokploy.com/docs/templates). Only expose what must be public via a domain.

## Expose & manage

- **Public URL:** attach a domain with `domain.create` keyed by `composeId` + `serviceName` + `port` — see [domains-tls.md](domains-tls.md).
- **Update:** `compose.redeploy`. **Stop/disrupt:** `compose.stop`, `compose.cancelDeployment`, `compose.killBuild` — see [safety.md](safety.md).
