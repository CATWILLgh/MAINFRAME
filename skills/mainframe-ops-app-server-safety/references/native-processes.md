# Native processes and managed services

Use the target platform's read-only process and listener tools. Exact commands
are adapter and operating-system details; do not assume Unix utilities exist
everywhere.

## Prove ownership

Correlate as many applicable signals as needed:

- PID and process start time;
- effective user;
- full command and arguments, with sensitive values redacted from output;
- current working directory;
- parent process, children, session, and process group;
- listening address, port, or socket;
- project-owned PID file, if the project genuinely maintains one;
- native process-manager identity and status.

On macOS or Linux, tools such as `lsof` and `ps` may provide these observations.
On Linux, `/proc/<pid>` may add cwd and process-tree evidence. On Windows, use
the documented native process and TCP-connection interfaces. Adapt commands to
the installed platform rather than copying an unavailable example.

Do not identify ownership from a universal process-name regex. Common names
such as `node`, `python`, `vite`, or `uvicorn` can belong to unrelated projects.
An occupied port is evidence of a listener, not proof of ownership.

Before signalling, repeat identity checks that can change, including PID start
time or command and cwd. This reduces the risk of acting on a reused PID.

## Respect the manager

When a process is owned by systemd, launchd, PM2, a development supervisor, an
app terminal, or another process manager, use that manager's documented
lifecycle operation. Killing a child directly may leave the manager running,
trigger replacement, or preserve the actual listener.

Shell and package-manager launchers can spawn a child that owns the socket.
Inspect the process tree and determine whether graceful shutdown should target
the service, parent, process group, or child according to the project's actual
launch model.

## Stop safely

Do not use broad name- or pattern-based termination such as `pkill -f`,
`killall`, or killing every process associated with a port. Target only the
resolved instance.

For an unmanaged Unix process, use SIGTERM first unless the application
documents another graceful signal. Wait for its normal shutdown window, then
verify the PID, children, process group, and listener are gone. A released port
alone does not prove every child exited; an exited parent alone does not prove
the listener stopped.

SIGKILL bypasses cleanup and can interrupt writes or leave related state. It is
a separate escalation after graceful shutdown fails, not the default final
step of every restart.
