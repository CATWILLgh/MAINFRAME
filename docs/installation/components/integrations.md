# Adapt integrations, runtime, settings, and permissions

Use this guide for `mcp`, `plugins`, `runtime`, `settings`, and for native support
required directly by another listed component.

## Inventory remains authoritative

An empty category means MAINFRAME currently installs no component of that kind.
Do not populate it from available marketplaces, old adapters, archives, or
nearby configuration. A runtime executable required by a listed hook supports
that hook; it does not gain a new inventory row.

Reuse compatible native tools and runtimes. Install only what an active listed
component requires. Never install development harnesses, test fixtures,
telemetry collectors, optional integrations, or generated adapters by default.

## MCP and external capabilities

Prepare protected credential delivery before registering a server. Use the
target's documented field names and secret references. Merge by stable server
identity and preserve unrelated registrations.

Verify native discovery and a harmless capability listing without printing
commands, headers, tokens, environment values, or protected paths. A process
that starts successfully does not prove tool exposure or authentication.

## Permissions

Apply the narrowest global permission that represents the canonical component's
actual boundary. A prompt rule is not a replacement for an enforceable native
permission. Record what is enforced and what remains instructional.

For `mainframe-harness-feedback`, grant access only to
`<MAINFRAME_ROOT>/docs/tickets/open/observations/` when the product can express
that path. Do not grant the whole repository, and do not create the directory
until the first real report requires it.

Never weaken a user's broader security policy to make MAINFRAME pass. If a
required capability conflicts with managed policy, preserve the policy and mark
the component pending or unsupported with the exact reason.

## Settings and cleanup

Merge settings by stable native key. Preserve user-owned values and effective
precedence. Remove an obsolete MAINFRAME-owned registration only after its
replacement is natively verified. Keep application caches and session data;
remove only installation staging and positively identified residue.
