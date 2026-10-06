# Optional Docker/Compose adapter

## Identity and authority

Establish which daemon the application actually contacts, its deployment location,
transport and environment. Docker CLI contexts, flags and environment overrides
may select a remote daemon; a custom SDK/HTTP client may ignore them entirely.
Inspect that client's configuration too. A local Unix socket or localhost address
can be a forwarding proxy/tunnel, so neither proves the managed resources are local.
Do not silently fall back to another daemon when the configured target is unavailable.
Show a safe target identity in the UI without credential-bearing endpoint URLs.

Do not add a Docker socket to the application merely for convenience. A `:ro`
bind mount of the socket does not filter HTTP methods or make Engine access
read-only. Prefer an existing narrowly authorized collector/broker. If introducing
one, enforce endpoint, method and resource policy at that boundary and document its
remaining privileges. An application allowlist does not limit what a compromised
process can do through a directly mounted unrestricted socket. Deployment of that
privilege requires an explicit scope decision, not a routine page implementation.

Use the actual Engine API capability/version; negotiate or validate supported
versions instead of hardcoding a supposedly universal minimum. Unix sockets,
Windows named pipes and authenticated remote transports are distinct implementations.
Do not advertise support for a transport only because its path is configurable.

## Resource scope and actions

Resolve configured project/tenant ownership on the server. Restrict list, inspect,
logs, statistics and mutations consistently. A Compose service name alone is not
unique across projects. Resolve stable container IDs, verify project/owner labels
and check current identity immediately before mutation; a guessed foreign ID or
name must fail even if it is absent from the UI list. Labels aid selection but
are not an authorization system independent of who can create those labels.

Keep start/stop/restart disabled unless required. Define per-action permissions,
CSRF/origin controls, allowed targets, critical-service policy and bounded timeouts.
Protect the console's own service and shared dependencies from accidental lockout.
A confirmation dialog is not server authorization. Serialize conflicting actions;
a timeout after submission means unknown outcome, requiring reread/reconciliation
rather than an automatic repeat restart. An accepted action is not confirmed
readiness: observe the requested state and applicable health separately.

Audit actor, environment, stable target, action, time and bounded outcome without
secret-bearing errors. Do not expose arbitrary Engine passthrough, exec, archive,
container creation, privileged mounts or command execution under a diagnostics API.

Image cleanup is separately authorized, off by default and limited to explicitly
identified candidates. Account for stopped containers, shared images and rollback
needs. Engine 'unused' does not mean operationally disposable. Revalidate before
removal, use no force and no broad prune as a substitute for selected IDs. Report
per-image results; shared layers mean summing image sizes does not prove freed disk.

## Compose and logs

Project configuration and deployed state are distinct. A file baked into an image
is a versioned configuration artifact, not proof of effective runtime settings.
Reuse Compose's documented merge/interpolation semantics where needed, including
version-specific reset/override tags; do not claim a custom YAML merge is equivalent.
Never execute untrusted config merely to render its contents.

Display an allowlisted structured projection by default. Raw YAML, literal env
values, interpolation defaults, labels, build arguments and healthcheck commands
can contain secrets. Showing only env key names elsewhere does not sanitize raw
files. Avoid resolved-config dumps; redact before API serialization/logging/cache,
and omit fields whose safe projection cannot be established. Logs/inspect output
also require restricted access and disclosure policy, not just truncation.

## Primary references

Reviewed 2026-10-04; refresh for the target version:

- [Contexts and overrides](https://docs.docker.com/engine/manage-resources/contexts/)
- [Daemon access](https://docs.docker.com/engine/security/protect-access/)
- [Socket limitations](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html#rule-1-do-not-expose-the-docker-daemon-socket-even-to-the-containers)
- [Engine API](https://docs.docker.com/reference/api/engine/)
- [Compose merge rules](https://docs.docker.com/reference/compose-file/merge/)
