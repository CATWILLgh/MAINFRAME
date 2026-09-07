# Dokploy safety

Classify the operation by its real effects, not its endpoint name or HTTP
method:

- access loss: API keys, users, SSO, Git providers, registries, SSH keys;
- shared infrastructure: servers, clusters, queues, Traefik, Redis, platform
  settings;
- data loss or cascade: projects, environments, applications, Compose stacks,
  databases, volumes, destinations, certificates, and backups;
- downtime: stop, reload, rebuild, redeploy, queue cancellation, process kill;
- routing and trust: domains, ports, redirects, TLS, certificates;
- recovery: restore and rollback operations that replace current state.

Reads are not automatically safe to disclose. Logs, environment views, API
specifications, and resource responses can contain credentials or private data.

Before a consequential operation:

1. Read and identify the exact resource and parent hierarchy.
2. Verify the target instance and current schema.
3. Enumerate affected children and consumers where a cascade is possible.
4. Confirm the active task covers that exact resource and effect.
5. Establish a usable rollback or recovery path and its data boundary.
6. Apply one narrow operation and wait for its terminal state.
7. Re-read the resource and verify service and user-facing behavior.

Do not treat a deployment rollback as data recovery. Do not assume deletion has
undo or dry-run. Do not expand authority from a child resource to its parent,
sibling, environment, or whole instance.
