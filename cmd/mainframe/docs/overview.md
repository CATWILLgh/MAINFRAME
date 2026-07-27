# MAINFRAME overview

MAINFRAME is a terminal application for installing, updating, and configuring
supported coding environments from one consistent interface.

Run `mainframe` with no arguments to open the terminal interface. Its first
screen is an overview of configuration areas rather than an installation
wizard that writes as it goes.

The terminal interface follows one visible transaction:

1. Choose adapters and optional features.
2. Configure MCP connections, credentials, and additional settings.
3. Review one complete plan.
4. Confirm that exact plan.
5. Apply it through the recoverable transaction boundary.

No installation or configuration change happens merely by opening a screen or
changing a choice. Those changes are written only after the final preview and
confirmation.

Secret entry is deliberately separate. After its own explicit confirmation,
the masked value is stored directly through the secret helper so it is
available to the later installation plan. The value is never shown in that
plan.

When a requested combination is not yet supported for application, MAINFRAME
keeps the plan read-only and explains the limitation.

Use `mainframe docs list` to see every topic included with this executable.
Use `mainframe --help` or contextual `--help` for concise command syntax.
