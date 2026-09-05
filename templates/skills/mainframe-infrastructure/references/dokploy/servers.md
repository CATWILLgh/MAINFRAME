# Servers (multi-node)

By default Dokploy deploys to the host it runs on. Additional **remote servers** let you deploy across nodes. Endpoints are under `server.*`; container-level operations on a node are under `docker.*`; Swarm clustering under `cluster.*` / `swarm.*`.

Server and cluster mutations have instance-wide blast radius. Verify the exact
schema and target against the installed instance before every write.

## List & inspect

```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G -H "x-api-key: $DOKPLOY_API_KEY" "$DOKPLOY_URL/api/server.all"
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -G -H "x-api-key: $DOKPLOY_API_KEY" \
  --data-urlencode "serverId=<id>" "$DOKPLOY_URL/api/server.one"
```

Other reads by `serverId`: `server.publicIp`, `server.getServerTime`, `server.security`, `server.validate`. Note: `server.getServerMetrics` takes a monitoring `url` + `token` + `dataPoints`, **not** a `serverId` — enable monitoring first (`server.setupMonitoring`) and pull its params via live-spec.

## Add a remote server

1. Register an SSH key first (`sshKey.*`), then create the server with its connection details:
```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{
  "name":"node-2","description":"","ipAddress":"<ip>","port":22,"username":"root",
  "sshKeyId":"<id>","serverType":"deploy"}' "$DOKPLOY_URL/api/server.create"
```
2. `server.setup` provisions it and `server.validate` checks readiness. Do not
   assume remote monitoring is available: current product documentation says it
   is unsupported for remote servers even though some API versions expose
   monitoring-related endpoints. Verify the target version and server type.

Do not maintain a hardcoded package checklist for remote servers. Let the target
version's `server.setup` and `server.validate` establish its requirements.
Current product documentation distinguishes deployment servers from build
servers; build servers compile Applications but do not host containers and are
not supported for Compose deployments.

## Containers & cluster

- **Containers on a node:** `docker.*` — inspect/list, plus `docker.restartContainer`, `docker.stopContainer`, `docker.killContainer`, `docker.removeContainer` (destructive — [safety.md](safety.md)). Pull exact endpoints via live-spec.
- **Swarm workers:** `cluster.addWorker` / `cluster.removeWorker`, `cluster.*`. `cluster.removeWorker` and `server.remove` are infrastructure-level — see [safety.md](safety.md).

Target a deploy at a specific node by setting `serverId` on `application.create` / `compose.create` / `*.create` for databases.
