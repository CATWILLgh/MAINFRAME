---
name: mainframe-secrets
description: Safely discover and consume credentials already registered on this machine without reading, echoing, logging, copying, or persisting their values. Use when a command, remote service, HTTP request, SSH connection, deployment, or external CLI needs a credential or a registered service description.
---

# Secrets handling

Use the installed credential mechanism without bringing secret values into model context.

## Discover a credential

- Read the [credentials index](~/.codex/credentials-index.md) for service names, credential identifiers, access commands, and non-secret operational notes.
- Treat the index as the only readable credential catalog.
- Never read, search, print, summarize, or copy the protected store under `~/.config/credentials/`.

## Consume a value

Follow the exact name and access pattern in the index. Pass the value directly to the process that needs it, for example:

```bash
curl -H "x-api-key: $(secret get REGISTERED_NAME)" https://example.invalid/
```

Never run `secret get` as a standalone inspection command. Do not echo, log, serialize, retain, or place a value in a response, ticket, commit message, diagnostic trace, or URL. Prefer credential-aware files, environment delivery, or stdin when a process argument could expose the value.

If the index has no suitable entry, return the exact missing credential or catalog entry to the immediate caller. Do not invent a name, search other projects for a value, or create persistent credential state. Credential-store administration remains outside agent execution.

Verify only whether the consuming operation succeeded. Return redacted evidence such as status, resource identity, or error class.
