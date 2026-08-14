# Containers

Preserve the runtime already used by the project. Docker Engine and Docker
Compose use Docker's CLI and daemon; Apple's `container` runs OCI-compatible
images as lightweight virtual machines on supported Macs. Do not translate a
command between them from a similar name. Check the installed runtime version
and its current primary documentation first.

Inspect the project's Dockerfile or Containerfile, ignore files, Compose files
when present, image source, runtime user, mounts, networks, health checks, and
deployment platform before changing them.

Choose hardening from the actual threat and operating model:

- keep secrets out of build context, layers, arguments, image metadata, and
  committed Compose environment values;
- use a non-root runtime user unless a demonstrated operation requires root;
- keep the final image and installed packages no larger than the application
  needs; use multi-stage builds when they remove build-only material;
- avoid `latest`; choose a reproducible version policy that the project's
  update process can actually maintain. Digest pinning is not mandatory when it
  would silently defeat the project's intentional update mechanism;
- add a health check only when it observes a meaningful service guarantee and
  the hosting platform uses it correctly;
- avoid privileged mode and unnecessary capabilities; prefer read-only
  filesystems only when the application's legitimate writes are mapped.

For Docker, ordinary container and image removal is local lifecycle work.
Volume removal, `compose down -v`, system-wide pruning, privileged execution,
and registry publication cross separate data, machine, or external boundaries.

For Apple `container`, ordinary container and image deletion or pruning is
local lifecycle work. Volume deletion or pruning, container-machine deletion,
uninstall with user-data deletion, and registry publication cross separate
data, machine, or external boundaries. `container system stop` is reversible
local lifecycle work and does not itself delete user data. Use the installed
CLI help because the command surface is versioned.

Before starting or restarting a local runtime or Compose stack, load
`mainframe:ops-app-server-safety` and inspect the existing project state. Do
not create a second stack merely to test configuration.

For a failing container, inspect its runtime-native state, health and logs,
then broader runtime events or services when lifecycle cycling remains
unexplained. Verify the concrete failure hypothesis rather than rebuilding
repeatedly.

Sources:

- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Dockerfile reference: https://docs.docker.com/reference/dockerfile/
- Docker Compose reference: https://docs.docker.com/reference/cli/docker/compose/
- Apple container 1.2.0: https://github.com/apple/container/releases/tag/1.2.0
- Apple container command reference: https://github.com/apple/container/blob/1.2.0/docs/command-reference.md
- OWASP Docker Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html
