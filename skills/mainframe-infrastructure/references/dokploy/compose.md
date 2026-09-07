# Dokploy Compose and Stack resources

Resolve whether the resource uses Docker Compose or Docker Stack/Swarm. Validate
the actual Compose file with the applicable engine and inspect source, project
name, environment interpolation, secrets, mounts, networks, ports, health
checks, and persistent data before changing it.

Determine whether configuration is inline, provider-backed, or repository
backed. Do not assume a source update preserves local files or relative bind
mounts. Verify the target version's source and deployment behavior.

Environment values stored by the platform are not necessarily injected into
containers unless the Compose file references or loads them. Inspect the
rendered configuration without exposing secret values.

Before mutation, obtain the live schemas for the exact Compose operation and
identify every affected service. Deployment is asynchronous: follow it to a
terminal state, inspect only relevant service logs, and verify each changed
service plus the routed product contract.

Treat stop, rebuild, queue cancellation, container removal, volume changes, and
Stack topology changes according to [safety.md](safety.md).
