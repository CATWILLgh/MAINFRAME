# Servers (multi-node)

By default Dokploy deploys to the host it runs on. Additional **remote servers** let you deploy across nodes. Endpoints are under `server.*`; container-level operations on a node are under `docker.*`; Swarm clustering under `cluster.*` / `swarm.*`.

```bash
H=(-H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json")
```

## List & inspect

```bash
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" "$DOKPLOY_URL/api/server.all"
curl -sS --fail-with-body -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "serverId=<id>" "$DOKPLOY_URL/api/server.one"
```

Other reads by `serverId`: `server.publicIp`, `server.getServerTime`, `server.security`, `server.validate`. Note: `server.getServerMetrics` takes a monitoring `url` + `token` + `dataPoints`, **not** a `serverId` — enable monitoring first (`server.setupMonitoring`) and pull its params via live-spec.

## Add a remote server

1. Register an SSH key first (`sshKey.*`), then create the server with its connection details:
```bash
curl -sS --fail-with-body "${H[@]}" -d '{
  "name":"node-2","description":"","ipAddress":"<ip>","port":22,"username":"root",
  "sshKeyId":"<id>","serverType":"deploy"}' "$DOKPLOY_URL/api/server.create"
```
2. `server.setup` provisions it; `server.validate` checks readiness; `server.setupMonitoring` enables metrics.

**Requirements for a deployment server** (per docs.dokploy.com/docs/core/remote-servers): Docker, RClone, Nixpacks, Railpack, and Buildpacks installed; Docker Swarm initialized; the Dokploy network created; and a designated main directory for application storage. `server.setup` handles this; `server.validate` reports gaps.

## Containers & cluster

- **Containers on a node:** `docker.*` — inspect/list, plus `docker.restartContainer`, `docker.stopContainer`, `docker.killContainer`, `docker.removeContainer` (destructive — [safety.md](safety.md)). Pull exact endpoints via live-spec.
- **Swarm workers:** `cluster.addWorker` / `cluster.removeWorker`, `cluster.*`. `cluster.removeWorker` and `server.remove` are infrastructure-level — see [safety.md](safety.md).

Target a deploy at a specific node by setting `serverId` on `application.create` / `compose.create` / `*.create` for databases.
