# Containers

Inspect the project's Dockerfile, `.dockerignore`, Compose files, image source,
runtime user, mounts, networks, health checks, and deployment platform before
changing them. Confirm current syntax and version-sensitive flags from Docker's
official documentation or Context7.

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

Before starting or restarting Compose, load `mainframe:ops-app-server-safety`
and inspect the existing project state. Do not create a second stack merely to
test configuration.

For a failing container, inspect in order: application or Compose logs,
`docker inspect` state and health history, then daemon events when lifecycle
cycling remains unexplained. Verify the concrete failure hypothesis rather than
rebuilding repeatedly.

Sources:

- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Dockerfile reference: https://docs.docker.com/reference/dockerfile/
- Docker Compose reference: https://docs.docker.com/reference/cli/docker/compose/
- OWASP Docker Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html
