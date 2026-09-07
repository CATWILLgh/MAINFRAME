---
name: mainframe-ops-app-server-safety
description: Prevent duplicate or disruptive local application servers. Use before starting, restarting, or stopping a long-running native process, managed service, or Compose stack; do not use for one-shot build, test, lint, or inspection commands.
---

# Local application server safety

Discovery does not grant authority to start, stop, restart, or reconfigure a
process. Use only the target and lifecycle requested by the active task.

## Establish identity and lifecycle

Before launching a long-running process, resolve:

- project root and expected working directory;
- exact command, service, process manager, or Compose project;
- expected user and relevant parent or process group;
- listener port, socket, service name, or container when known;
- intended lifetime: temporary verification, current task, or leave running;
- readiness signal, log source, and graceful shutdown mechanism.

For a native process or managed service, read
[native-processes.md](references/native-processes.md). For Docker Compose or a
compatible Compose runtime, read [compose.md](references/compose.md). Do not
apply one branch's lifecycle commands to the other.

## Decide from observed state

- If the exact intended instance is running and healthy, reuse it unless the
  task requires a restart or configuration change.
- If a similar process is visible but ownership is not proven, do not stop it
  or start a conflicting instance. Report the missing identity evidence.
- If the intended instance exists but is unhealthy, do not create a duplicate.
  Diagnose within scope and restart only when the task authorizes it.
- If a resolved start was requested and no matching instance exists, launch it
  once without an extra approval round.
- If stop or restart was requested but no exact instance exists, report that
  fact. Do not silently convert restart into a fresh start.

A matching name, occupied port, live PID, or running container is only one
signal. It does not alone prove project ownership, health, or readiness.

## Start or restart

Immediately before a signal or lifecycle command, revalidate the exact target.
Prefer its documented process manager or graceful shutdown path. A restart
request covers only the resolved instance, not similarly named processes,
sibling services, or a broader stack.

After graceful shutdown, wait for the project-configured or documented window
and check the process tree, listener, and manager state again. Do not use force
termination by default. If shutdown fails, report the surviving target and the
consequence of escalation; use force only when that escalation is explicitly
authorized.

Launch or reconcile once. Do not enter an automatic restart loop.

## Verify readiness

Use the narrowest project-provided readiness signal: an expected socket,
bounded readiness command, declared health check, or documented endpoint. Do
not invent `/health`. Confirm that the listener belongs to the intended
process, notice early exit, and inspect only relevant bounded logs.

Keep the resolved command, cwd, identity, port or URL, lifecycle expectation,
and log source in active task context.

## Bind race

There is a race between preflight and the server binding its socket. A generic
shell lock cannot reserve a port for an arbitrary application. On
`EADDRINUSE`, do not retry in a loop: identify the new listener, prove its
ownership, then reuse the intended instance or report the conflict.
