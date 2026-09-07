# Containers

Identify the actual runtime and version before acting. Docker Engine, Docker
Compose, Podman, Apple Container, and platform-managed runtimes are not
interchangeable merely because they run OCI images.

Inspect the project Dockerfile or Containerfile, ignore rules, Compose or stack
files, build context, image source, runtime user, mounts, networks, ports,
health checks, and deployment platform.

Choose hardening from the real operating model:

- keep secrets out of build contexts, layers, arguments, image metadata, and
  committed Compose values;
- use a non-root runtime user unless a demonstrated requirement prevents it;
- remove build-only material from the final image when it materially reduces
  risk or size;
- use a reproducible version policy compatible with the project's update
  process; digest pinning is not automatically required;
- add health checks only when they measure a meaningful service guarantee and
  the hosting platform consumes them correctly;
- avoid privileged mode and unnecessary capabilities;
- use a read-only filesystem only when legitimate writes have explicit homes.

Before start, stop, restart, rebuild, removal, or pruning, inspect the existing
process, container, volume, network, listener, and project ownership. Determine
whether writable layers or volumes contain data. Local location alone does not
make a resource disposable or authorize deletion.

For failures, inspect runtime state, health, logs, events, dependencies, and
resource pressure before cycling or rebuilding. Test the concrete hypothesis
and target only the resolved project instance; do not use broad process-kill or
system-wide prune commands.

Use the installed runtime's primary documentation because commands and
lifecycle behavior are versioned.
