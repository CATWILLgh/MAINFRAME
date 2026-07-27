# Agent automation

Start every automated interaction by running:

```text
mainframe capabilities --json
```

The response is a versioned machine contract. It lists exact command syntax,
input and output channels, whether a command can write, the required
confirmation form, and the matching documentation topic. Do not scrape the
terminal interface or assume a command exists because another MAINFRAME
version had it.

Read detailed guidance with `mainframe docs show <topic>`. These commands are
embedded in the executable and work without opening adapter configuration or
resolving a release root.

For JSON commands, send exactly one document on standard input. Credential
commands declare `schema_version` and `kind` in their responses.
`mainframe plan` is the current exception: its response is an unversioned
object containing `operations`. This is stated explicitly here rather than
implied by the capability envelope. Treat a non-zero exit code and standard
error as failure. Never weaken or bypass a review/confirmation pair.

Never place a secret value in command arguments, JSON input, logs, or chat
transcripts. MAINFRAME's agent-facing credential interfaces use instance
metadata and secret references only. Secret value entry remains a direct human
action through the masked terminal interface.

`mainframe plan` is read-only. Credential-instance writes use the explicit
review and apply commands documented in the `credentials` topic. Other
installation changes should go through the terminal interface until the
capability response explicitly advertises a corresponding machine command.

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
