---
name: ops-app-server-safety
user-invocable: false
description: Prevent accidental duplicate native development servers and choose the least disruptive correct action for an existing Docker Compose project. Identifies the exact process or Compose project before start, restart, or stop operations.
when_to_use: Trigger when a task involves starting, restarting, or stopping a long-running development process or container stack. Signal commands include `npm run dev`, `npm start`, `yarn dev`, `pnpm dev`, `vite`, `next dev`, `nodemon`, `uvicorn`, `gunicorn`, `flask run`, `rails s`, `docker compose up`, `docker compose down`, `docker compose restart`. Signal phrases include "start the dev server", "launch the app", "restart the backend", "bring up docker compose".
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
   - One line per listener with PID and command name. Empty output → port free.
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
   - `docker compose ps --status running`
   - Non-empty → containers already up for this project.
3. **Choose by intended change.**
   - No restart or configuration change: use the running services.
   - Restart with unchanged Compose configuration: use
     `docker compose restart [SERVICE...]`.
   - Changed configuration or image: use `docker compose up -d [SERVICE...]`
     with the project's normal build or pull policy. Compose reconciles changed
     services; `restart` does not apply configuration changes.
   - Use `docker compose down` only when removal of the project's containers and
     networks is explicitly intended. It is not the default restart primitive.

Do not preflight a Docker stack by host port. Compose orchestrates a network of containers; a port conflict may be unrelated to this stack. `docker compose ps` is the correct probe.

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

The graceful-stop discipline follows twelve-factor app §IX Disposability: processes should shut down on SIGTERM. SIGKILL skips cleanup hooks and may leave state corrupted (open sockets, half-written files, dangling locks).

## After launch

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

Between preflight and start there is a race window: a third process can grab the port in the milliseconds between `lsof` returning empty and the dev server binding. Pure-shell defense against this is platform-specific — `flock` exists on Linux but not natively on macOS, and `open(2)` with `O_EXCL` is below the shell level. This skill does not cover that race. In practice: dev tools fail loudly with `EADDRINUSE` if the race materializes, so the failure is visible and recoverable by re-running.

## Sources

- [The Twelve-Factor App, processes](https://12factor.net/processes) and
  [disposability](https://12factor.net/disposability)
- [Docker Compose `up`](https://docs.docker.com/reference/cli/docker/compose/up/), [`restart`](https://docs.docker.com/reference/cli/docker/compose/restart/), and [`down`](https://docs.docker.com/reference/cli/docker/compose/down/)
- [`lsof(8)` manual](https://man7.org/linux/man-pages/man8/lsof.8.html)
