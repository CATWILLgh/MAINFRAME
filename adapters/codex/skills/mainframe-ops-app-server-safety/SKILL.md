---
name: mainframe-ops-app-server-safety
description: Prevent duplicate or disruptive local development servers and choose the least disruptive correct action for an existing Docker Compose project. Use before starting, restarting, or stopping a long-running process or container stack, including npm, yarn, pnpm, Vite, Next.js, nodemon, uvicorn, gunicorn, Flask, Rails, and Docker Compose commands.
---

# Server safety: no duplicate long-running processes

A preflight before launching dev servers, application processes, and container
stacks. Discovery does not grant permission to stop a process or mutate a
Compose project; use only the authority supplied by the active task.

## Rule

Before launching a long-running process, establish its expected working
directory, command or Compose project, and port or service when known. Reuse an
already-running matching instance unless the task requires a restart or a
configuration/image change. Never stop a process merely because its name or
port looks similar.

## Preflight — native processes

Applies to: dev servers like `vite`, `next dev`, `nodemon`, `uvicorn`, `gunicorn`, `flask run`, `rails s`, custom application servers.

1. **Check the port if known.**
   - macOS / Linux: `lsof -nP -iTCP:<PORT> -sTCP:LISTEN`
   - One line per visible listener with PID and command name. Empty output means
     no listener was visible at that instant; it is not durable ownership of
     the port.
2. **Check the process by command** (fallback or in addition).
   - macOS / Linux: `ps -ef | grep -E 'vite|next dev|nodemon|uvicorn|gunicorn|flask run|rails s' | grep -v grep`
   - If multiple projects on the host could host similar processes, disambiguate by working directory: `ps -o pid,command -p <PID>` and `lsof -p <PID> | grep cwd`.

3. **Prove ownership before acting.** Confirm the PID's working directory and
   full command. A regex match alone may belong to another project or session.
   A project-provided PID file or process manager is valid evidence when the
   repository actually uses one.

## Preflight — Docker Compose

Applies to any `docker compose up` invocation.

1. **Resolve the intended Compose file, project name, and working directory.**
   Do not let an incidental current directory select the target.
2. **Check existing containers for this compose project.**
   - Run the resolved project command with
     `ps --status running --services`.
   - One or more service-name lines means those services are running. The
     default table output is not a valid emptiness check because it includes a
     header even when there are no matching containers.
3. **Choose by intended change.**
   - No restart or configuration change: use the running services.
   - Restart with unchanged Compose configuration: use
     `docker compose restart [SERVICE...]`.
   - Changed configuration or image: use `docker compose up -d [SERVICE...]`
     with the project's normal build or pull policy. Compose reconciles changed
     services; `restart` does not apply configuration changes.
   - Use `docker compose down` only when removal of the project's containers and
     networks is explicitly intended. It is not the default restart primitive.

Do not use a host port as proof that a Docker container belongs to the intended
Compose project. Resolve ownership with `docker compose ps`; use a port check
only as separate evidence of a possible bind conflict.

## When already running

- Do not start a second instance.
- Return what is running: `<command> @ pid <PID>` on port `<PORT>` (native), or `<service-name> @ <container-id>` (compose).
- If the task can be completed against the existing instance (open a URL, hit a healthcheck, read logs) — use it.

## When a restart is explicitly requested

1. **Confirm the matched target and restart authority.** A restart request
   authorizes stopping that exact instance, not a similarly named process or a
   broader Compose project.
2. **Stop gracefully first** — send SIGTERM, not SIGKILL.
   - Native: `kill <PID>` (default SIGTERM).
   - Compose with unchanged configuration: `docker compose restart [SERVICE...]`.
3. **Wait for the target's documented or project-configured shutdown window.**
   Re-check with the same preflight evidence.
4. **Do not force-kill by default.** If graceful shutdown fails, return the
   exact still-running target and the consequence of forced termination to the
   immediate caller. Use SIGKILL or `docker compose kill` only when that
   escalation is explicitly authorized.
5. **Launch or reconcile once.** Do not loop.

The graceful-stop discipline follows twelve-factor app §IX Disposability:
processes should finish or release current work on SIGTERM. SIGKILL bypasses
that shutdown path and can interrupt in-flight work.

## After launch

Verify readiness with the narrowest project-provided signal: a health endpoint,
an expected listening socket, a bounded existing readiness command, or Compose
health/status. A live PID or container alone proves only that the process
exists. Keep the check bounded and do not invent an endpoint the project does
not define.

Keep in the active task context:
- The exact command used and its working directory (`cwd`).
- The port or URL the process serves.
- Where logs are written (stdout, file, container log).

Subsequent steps (open a URL, run a test, query the API) need this context; re-discovering it from scratch wastes turns. Record once.

## Stop conditions

- If the target cannot be identified from the task, repository, or process
  evidence, do not start or stop anything. Return the exact missing identifier
  to the immediate caller.
- If the task is to start a resolved application and no matching instance is
  running, launch it without an extra confirmation round.
- If the task is to restart or stop an existing instance but no exact match is
  running, return that fact. Do not silently turn a restart into a fresh start;
  the named instance may belong to another project or environment.

## Known limitation

Between preflight and the server's own socket bind there is a race window: a
different process can claim the port. A shell lock coordinates only launchers
that voluntarily share that lock; it cannot reserve the TCP port for an
arbitrary server. Treat `EADDRINUSE` as a visible recoverable conflict, identify
the new listener, and do not enter an automatic restart loop.

## Sources

- [The Twelve-Factor App, processes](https://12factor.net/processes) and
  [disposability](https://12factor.net/disposability)
- [Docker Compose `up`](https://docs.docker.com/reference/cli/docker/compose/up/), [`restart`](https://docs.docker.com/reference/cli/docker/compose/restart/), and [`down`](https://docs.docker.com/reference/cli/docker/compose/down/)
- [Docker Compose `ps`](https://docs.docker.com/reference/cli/docker/compose/ps/)
- [`lsof(8)` manual](https://man7.org/linux/man-pages/man8/lsof.8.html)
