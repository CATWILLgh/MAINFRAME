# Adapters and MCP

An adapter is MAINFRAME's integration with one coding environment. Claude
Code, Codex, OpenCode, and standalone Antigravity 2.x remain separate
installation targets. Each adapter owns its own files and runtime-specific
projection; one adapter does not use another adapter's configuration directory.

The terminal interface can select adapters independently. Removing one adapter
from the desired state does not imply removing the others.

The public adapter identifiers supported for direct desired selection are:

```text
antigravity-2
claude-code
codex
opencode
```

MAINFRAME adds their internal delivery dependencies automatically. Do not place
internal component names in a user selection.

The current optional feature identifier is `dev.harness-feedback`. It is part
of developer diagnostics and has no independent meaning when developer mode is
disabled.

MCP connections are configured only after at least one adapter is selected.
The same neutral MCP choice can be projected into several selected adapters,
but every adapter receives its own native configuration. MAINFRAME shows the
adapter-specific storage or capability difference before application.

Context7 is the first catalogued MCP service. Keyed and keyless profiles are
separate choices. A credential instance can be reused by several supported
projections without copying its value into MAINFRAME's catalog.

Standalone Antigravity 2.x and Antigravity IDE are different products.
MAINFRAME's Antigravity adapter targets only the known standalone 2.x
configuration.
