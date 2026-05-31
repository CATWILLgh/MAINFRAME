---
name: ops-app-server-safety
user-invocable: false
allowed-tools: Bash
description: Prevent duplicate instances of long-running development processes (dev servers, application processes, Docker Compose stacks). Run a preflight check before launching to detect an already-running instance by port or process name; if already running, do not start a second one. Handle restarts by stopping the current instance gracefully (SIGTERM, escalate to SIGKILL only on timeout) before launching once.
when_to_use: Trigger when a task involves starting, restarting, or stopping a long-running development process or container stack. Signal commands include `npm run dev`, `npm start`, `yarn dev`, `pnpm dev`, `vite`, `next dev`, `nodemon`, `uvicorn`, `gunicorn`, `flask run`, `rails s`, `docker compose up`, `docker compose down`, `docker compose restart`. Signal phrases include "start the dev server", "launch the app", "restart the backend", "bring up docker compose".
---

# Server safety: no duplicate long-running processes

A preflight gate before launching dev servers, application processes, and container stacks. Prevents the most common operational failure mode: a second instance fighting the first for the port, mid-state, or shared volumes.

## Rule

Before launching a long-running process (dev / start / serve, container `up`), run preflight first. If an instance is already running, use it — do not start a second. If a restart is explicitly requested, stop the current instance gracefully, then launch once.

## Preflight — native processes

Applies to: dev servers like `vite`, `next dev`, `nodemon`, `uvicorn`, `gunicorn`, `flask run`, `rails s`, custom application servers.

1. **Check the port if known.**
   - macOS / Linux: `lsof -nP -iTCP:<PORT> -sTCP:LISTEN`
   - One line per listener with PID and command name. Empty output → port free.
2. **Check the process by command** (fallback or in addition).
   - macOS / Linux: `ps -ef | grep -E 'vite|next dev|nodemon|uvicorn|gunicorn|flask run|rails s' | grep -v grep`
   - If multiple projects on the host could host similar processes, disambiguate by working directory: `ps -o pid,command -p <PID>` and `lsof -p <PID> | grep cwd`.

PID files are **not** used here — modern dev tools rarely write them, and the twelve-factor app (§VIII Concurrency) explicitly recommends against manual PID-file management.

## Preflight — Docker Compose

Applies to any `docker compose up` invocation.

1. **Check existing containers for this compose project.**
   - `docker compose ps --status running`
   - Non-empty → containers already up for this project.
2. **If running and recreate was not requested** — do not call `docker compose up` again. Use the existing stack (logs, healthchecks, URLs).
3. **If launching anyway** — prefer `docker compose up --no-recreate` to avoid rebuilds when configuration is unchanged.

Do **not** preflight a Docker stack by host port. Compose orchestrates a network of containers; a port conflict may be unrelated to this stack. `docker compose ps` is the correct probe.

## When already running

- Do not start a second instance.
- Report what is running: `<command> @ pid <PID>` on port `<PORT>` (native), or `<service-name> @ <container-id>` (compose).
- If the task can be completed against the existing instance (open a URL, hit a healthcheck, read logs) — use it.

## When a restart is explicitly requested

1. **Stop gracefully first** — send SIGTERM, not SIGKILL.
   - Native: `kill <PID>` (default SIGTERM).
   - Compose: `docker compose down` (sends SIGTERM to containers, escalates to SIGKILL after its own timeout).
2. **Wait briefly** — give the process up to ~10 seconds to shut down. Re-check with the same preflight commands.
3. **Escalate only on timeout** — `kill -9 <PID>` or `docker compose kill` only if SIGTERM did not work in the allotted window.
4. **Launch once.** Do not loop.

The graceful-stop discipline follows twelve-factor app §IX Disposability: processes should shut down on SIGTERM. SIGKILL skips cleanup hooks and may leave state corrupted (open sockets, half-written files, dangling locks).

## After launch

Record for the rest of the session:
- The exact command used and its working directory (`cwd`).
- The port or URL the process serves.
- Where logs are written (stdout, file, container log).

Subsequent steps (open a URL, run a test, query the API) need this context; re-discovering it from scratch wastes turns. Record once.

## Stop conditions

- If port / command / service is unclear from context, ask **one** clarifying question before running anything. Do not guess.
- If a specific process was named but preflight finds nothing related, surface that ("no `vite` process or listener on :5173 found") before starting — it may be a different project or environment.

## Known limitation

Between preflight and start there is a race window: a third process can grab the port in the milliseconds between `lsof` returning empty and the dev server binding. Pure-shell defense against this is platform-specific — `flock` exists on Linux but not natively on macOS, and `open(2)` with `O_EXCL` is below the shell level. This skill does not cover that race. In practice: dev tools fail loudly with `EADDRINUSE` if the race materializes, so the failure is visible and recoverable by re-running.

## Sources

- The Twelve-Factor App, §VI Processes / §VIII Concurrency / §IX Disposability — https://12factor.net/
- Docker Compose CLI reference (`up`, `ps`, `down`) — https://docs.docker.com/reference/cli/docker/compose/up/
- `lsof(8)` man page — https://man7.org/linux/man-pages/man8/lsof.8.html

Internal: §E source check by sub-agent on 2026-05-28 — see ADR 0028.
