# Compose projects

Use the installed Compose-compatible runtime's current documentation and
project-native command. Do not assume Docker Compose syntax for another
runtime.

## Resolve the project

Before a lifecycle command, establish:

- every Compose file and override in the intended order;
- project directory and effective project name;
- environment-file inputs without exposing secret values;
- selected profiles and target services;
- current target containers and ownership labels; inspect ports, health, networks,
  and volumes when needed to identify the target or assess the operation's effects.

Run status inspection with the same resolved project arguments that the
lifecycle command would use. Prefer Compose project labels and metadata for
ownership. A host port is only separate conflict evidence and can belong to an
unrelated stack.

Do not create a second stack by accidentally changing cwd, project name,
Compose files, or profiles.

## Choose the matching lifecycle operation

- Reuse healthy running services when no lifecycle or configuration change was
  requested.
- Use the runtime's restart operation only when configuration, environment,
  image, mounts, and topology are unchanged. Restart does not apply most
  configuration changes.
- When configuration or image state changed, use the project's normal
  reconciliation command and determine which services it may recreate, build,
  or pull before execution.
- Stop and down are not equivalent. Down can remove project containers and
  networks and is not a routine restart primitive.
- Never add volume deletion, force kill, orphan removal, image removal, or
  system-wide pruning without authority for that exact effect.

Inspect persistent volumes and writable container state before any removal or
recreation that may affect data.

## Verify

Verify the requested lifecycle outcome on the exact project and services. After
start or restart, check relevant health, listeners, and the application route
when readiness is required; command success alone does not prove readiness.
After stop or removal, verify the intended targets stopped or were removed and
resources that should be preserved remain. Do not require a stopped route to respond.

If the runtime reports a port conflict, identify the listener separately and
prove ownership. Do not stop it or change the Compose project name merely to
make the stack start.
