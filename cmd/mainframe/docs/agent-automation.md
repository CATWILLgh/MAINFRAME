# Agent automation

Start every automated interaction by running:

```text
mainframe capabilities --json
```

Local release delivery uses the same review and exact-apply boundary:

```sh
mainframe release review
mainframe release apply --confirm <digest>
```

The review input selects either an absolute local release directory or one
exact cached identity. Apply accepts only the unchanged normalized request
returned by review. Release hashes are integrity checks, not publisher
authentication.

The response is a versioned machine contract. It lists exact command syntax,
input and output channels, whether a command can write, the required
confirmation form, and the matching documentation topic. Do not scrape the
terminal interface or assume a command exists because another MAINFRAME
version had it.

Read detailed guidance with `mainframe docs show <topic>`. These commands are
embedded in the executable and work without opening adapter configuration or
resolving a release root.

For JSON commands, send exactly one document on standard input. Draft and
credential commands declare `schema_version` and `kind` in their responses.
`mainframe plan` is the current exception: its response is an unversioned
object containing `operations`. This is stated explicitly here rather than
implied by the capability envelope. Treat a non-zero exit code and standard
error as failure. Never weaken or bypass a review/confirmation pair.

Never place a secret value in command arguments, JSON input, logs, or chat
transcripts. MAINFRAME's agent-facing credential interfaces use instance
metadata and secret references only. Secret value entry remains a direct human
action through the masked terminal interface.

`mainframe draft review` safely observes the current installation and returns
the same adapter, configuration, MCP, and diagnostics plan used by the terminal
interface. When the exact plan is supported for machine application, the
response contains `command_available: true` and a secret-free confirmation
digest. Apply the unchanged request with:

```text
mainframe draft apply --confirm <digest>
```

Providing `--confirm` authorizes MAINFRAME to recover an unfinished transaction
before it rebuilds the current plan. A changed release, host layout, desired state, file identity,
configuration, or deferred secret reference makes the digest stale and
requires a new review. The digest is opaque: do not inspect or alter it.
The request describes the complete desired adapter and MCP state:

```json
{
  "schema_version": 1,
  "kind": "mainframe-draft",
  "desired": {
    "adapters": ["opencode"],
    "mcp": [
      {
        "server_id": "context7",
        "profile_id": "remote-api-key",
        "adapters": ["opencode"],
        "credential_instance_id": "context7-home"
      }
    ],
    "diagnostics_policy": "preserve-retained-adapters"
  }
}
```

Both arrays are required, including when empty. An omitted adapter or MCP
connection is intentionally planned for removal when MAINFRAME owns it.
Diagnostics stay unchanged on retained adapters and leave with a removed
adapter. Diagnostics cannot be enabled or reconfigured through this command.
Keyed profiles require `credential_instance_id`; keyless profiles reject it.
The field contains an existing instance identifier, never a value. The same
instance may be used for each currently supported adapter in one connection.

Review and apply deliberately do not start `codex app-server`; Codex external hook
trust is therefore reported as not assessed when it cannot be proven from
files. This keeps the command from changing Codex runtime state.

`mainframe plan` is the older release-model planner. It uses a caller-supplied
observed snapshot and may expose target locations; do not confuse it with live
machine observation. Credential-instance writes use the explicit review and
apply commands documented in the `credentials` topic. Other installation
Unsupported drafts remain review-only with `command_available: false`. Other
installation changes should go through the terminal interface.

The plan request is one strict JSON document:

```json
{
  "desired": {
    "components": ["opencode"],
    "features": []
  },
  "observed": {
    "components": []
  }
}
```

The public adapter and feature identifiers are listed in the
`adapters-and-mcp` topic included with the same executable. Do not use
`mainframe plan` as a filesystem discovery shortcut: `observed` is an explicit
caller-supplied snapshot, while the terminal interface performs its own safe
observation.
