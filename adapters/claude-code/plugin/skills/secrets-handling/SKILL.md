---
name: secrets-handling
user-invocable: false
description: Safely discover and consume credentials already registered on this machine without reading, echoing, logging, copying, or persisting their values. Uses the repository-owned credentials index for names and the `secret` helper or a native credential-aware tool for value delivery.
when_to_use: Use when a terminal command, remote service, HTTP request, SSH connection, deployment, or external CLI needs a credential or a server/service short-name. Not needed for work that neither discovers nor consumes credentials.
---

# Secrets handling

Use the installed credential mechanism without bringing secret values into
model context.

## Sources of truth

- Read the
  [credentials index](~/.claude/credentials-index.md)
  for service names, credential identifiers, access commands, and non-secret
  operational notes. The index contains no values and is the only credential
  catalog the model may read.
- Values live in the protected store under `~/.config/credentials/`. Never read,
  search, print, summarize, or copy that directory.
- The `secret` helper is the generic value-delivery interface. Native tools may
  use their own configured credential mechanism, such as `ssh`, `gh`, or
  `curl --netrc`, without exposing the backing files.

## Consume a registered value

Follow the exact credential name and access pattern in the index. Prefer direct
substitution into the process that needs the value:

```bash
curl -H "x-api-key: $(secret get REGISTERED_NAME)" https://example.invalid/
```

The shell substitutes the helper output into that process without returning the
value to the model. An already-exported environment variable may be passed
directly when the index names it, but do not assume every stored credential is
present in the current environment.

Never:

- run `secret get` as a standalone inspection command;
- echo, log, serialize, or interpolate a value into a response or file;
- assign a value to a shell variable that later diagnostic output could expose;
- place a value in a URL, command example, ticket, commit message, or process
  argument when a credential-aware file, environment, or stdin mechanism is
  available;
- weaken TLS, host-key, or certificate checks merely to make authentication
  succeed.

## Missing or external credentials

If the index has no suitable entry, do not invent a name, search other projects
or memory for a value, migrate a credential, or create persistent state. Return
the exact missing credential or catalog entry to the immediate caller. Adding
or relocating a credential requires explicit authority and a value supplied
through a protected terminal path, never through the conversation.
Credential-store administration (`set`, `del`, `edit`, and `list`) stays
outside agent execution; the global permission layer denies those helper modes.

## Evidence and output

Verify only whether the consuming operation succeeded and return redacted
evidence such as status, resource identity, or error class. Do not return
request headers, environment dumps, verbose traces, URLs with embedded auth, or
raw error bodies until they are known not to contain a value.

The global permission layer blocks direct reads of protected stores. The
[secret commit gate](../../hooks/scripts/secret-commit-gate.py) checks effective
commit content for high-confidence credential shapes. These are safety nets,
not permission to retrieve values into context.

For authenticated HTTP mechanics, use
[`curl-requests`](../curl-requests/SKILL.md). For infrastructure authority and
environment selection, use [`infrastructure`](../infrastructure/SKILL.md).
