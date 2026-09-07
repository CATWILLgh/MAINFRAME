# Dokploy servers and clusters

Determine whether the target is the Dokploy host, an independent deployment
server, a build server, or a Swarm node. These roles have different topology,
registry, storage, networking, and failure implications.

Inspect the current official documentation and live schema for server setup,
validation, monitoring, Docker operations, and cluster membership. Product
support differs by version and server type; do not preserve an old package
checklist or capability claim as permanent truth.

Before registration or setup, verify the address, SSH identity, host-key trust,
architecture, role, capacity, existing workloads, Docker state, firewall,
storage, and rollback route. Platform setup can install software and change
host networking; it is not a harmless connectivity test.

Build servers may require a registry and may support fewer deployment types
than deployment servers. Remote servers and Swarm nodes are different
architectures; do not interchange them because both add machines.

Server removal, cluster membership changes, container kill/removal, Traefik
changes, and shared cleanup have broad blast radius. Apply
[safety.md](safety.md), target one resolved resource, and verify both the node
and every affected application afterward.
