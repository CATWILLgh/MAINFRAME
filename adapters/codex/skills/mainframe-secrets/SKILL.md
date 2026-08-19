---
name: mainframe-secrets
description: Safely discover and consume credentials already registered on this machine without reading, echoing, logging, copying, or persisting their values. Use when a command, remote service, HTTP request, SSH connection, deployment, or external CLI needs a credential or a registered service description.
---

# Secrets handling

Use the installed credential mechanism without bringing secret values into model context.

## Sources of truth

- Read the [credentials index](../../../../shared/credentials/credentials-index.md) for service names, credential identifiers, access commands, and non-secret operational notes.
- Treat the index as the only readable credential catalog.
- Never read, search, print, summarize, or copy the protected store under `~/.config/credentials/`.
- Use the `secret` helper as the generic value-delivery interface. A native
  tool such as `ssh`, `gh`, or `curl --netrc` may use its configured credential
  mechanism without exposing the backing file.

## Consume a value

Follow the exact name and access pattern in the index. Pass the value directly to the process that needs it, for example:

```bash
secret run REGISTERED_NAME -- consumer-command
```

`secret run` removes other names from the managed store from the inherited
environment and exposes only the requested names to that one child process.
Prefer it whenever the consumer accepts credentials through environment
variables. If a consumer requires the value in a specific argument or header,
use the narrow inline form without printing it:

```bash
curl -H "x-api-key: $(secret get REGISTERED_NAME)" https://example.invalid/
```

Never run `secret get` as a standalone inspection command. Do not echo, log, serialize, retain, or place a value in a response, ticket, commit message, diagnostic trace, or URL. Prefer credential-aware files, environment delivery, or stdin when a process argument could expose the value.

An already-exported environment variable is usable only when the index names
it for the resolved service. Do not assign a value to a shell variable that a
later diagnostic could expose. Never weaken TLS, certificate, or SSH host-key
verification merely to make authentication succeed.

If the index has no suitable entry, return the exact missing credential or catalog entry to the immediate caller. Do not invent a name, search other projects or memory for a value, relocate a credential, or create persistent credential state. Credential-store administration remains outside agent execution and needs separately supplied authority and protected input.

Verify only whether the consuming operation succeeded. Return redacted evidence such as status, resource identity, or error class. Do not return request headers, environment dumps, verbose traces, authenticated URLs, or an unreviewed response body.

For authenticated HTTP mechanics, use
[`mainframe-curl-requests`](../mainframe-curl-requests/SKILL.md). For environment
selection and infrastructure authority, use
[`mainframe-infrastructure`](../mainframe-infrastructure/SKILL.md).
