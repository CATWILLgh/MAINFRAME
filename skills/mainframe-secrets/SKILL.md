---
name: mainframe-secrets
description: Locate, register, update, deliver, or return credentials through the centralized MAINFRAME index and installed secret mechanism. Use proactively when authentication is needed, a credential is supplied or requested, registration or removal is requested, or a command, service, deployment, HTTP request, SSH connection, MCP server, or external tool needs a credential. Credential availability never authorizes the consuming action.
---

# Credential handling

Use the installed credential mechanism without bringing protected values into
model-visible commands or output.

## Resolve the credential

- Read the centralized catalog at `{{CREDENTIALS_INDEX}}`. During adaptation,
  replace this marker with the target environment's path to the local
  `shared/credentials/credentials-index.md`.
- Treat the catalog as metadata only: service identities, addresses, credential
  names, access commands, and non-secret operational notes.
- Never read, search, print, summarize, diff, or archive the protected
  credential store.
- Do not use `secret list` for routine discovery. Use the catalog.
- Do not infer authority to perform an external action merely because a
  credential exists.

## Deliver the value to a consumer

Prefer an already configured native mechanism such as an SSH agent, `gh`
authentication, a system credential service, or a consumer-owned credential
file.

When the consumer accepts an environment variable, prefer process-scoped
delivery:

```bash
secret run REGISTERED_NAME -- consumer-command
```

This exposes only the requested registered names to that child process. Do not
load the complete store from shell startup files.

If the consumer requires a value in a specific input and no safer native,
environment, or stdin mechanism exists, nest `secret get REGISTERED_NAME`
directly inside that single consumer invocation. Never run `secret get` as a
standalone inspection command.

Never manually echo, log, serialize, retain, or place a value in a response,
prompt, ticket, URL, commit, patch, manifest, telemetry event, diagnostic trace,
model-authored shell variable, or temporary file. Avoid process arguments when
a safer delivery channel exists. Never weaken TLS, certificate, or SSH host-key
verification to make authentication succeed.

## Administer a credential

Treat an explicit instruction from your current recipient to register, update,
delete, or copy a specifically identified credential as authority for that
credential operation only. Do not add repeated confirmations, generic danger
warnings, or a refusal merely because the requested operation handles a
credential. This authority does not extend to an authenticated external action.

When the recipient says the value is in the clipboard, register or replace it
without inspecting the clipboard first:

```bash
secret set REGISTERED_NAME --clipboard
```

The command line and result contain only the registered name. The helper reads
the clipboard internally, rejects empty or multiline values, writes under its
concurrency lock, and leaves the clipboard unchanged. Do not turn the value
into a command argument, shell expansion, environment variable, temporary
file, diagnostic, or intermediate tool call.

If clipboard access is unavailable, use a recipient-controlled native secret
input when the adapter provides one. Otherwise use the interactive terminal
fallback:

```bash
secret set REGISTERED_NAME --prompt
```

Never simulate protected input by placing the value in a tool call. If the
recipient has already supplied a value in the conversation, do not repeat or
quote it. Continue through a protected transfer route when one is available, or
state the single required clipboard or prompt action without abandoning
unrelated work.

On an explicit retrieval request, deliver the registered value directly to the
recipient's clipboard without reading or printing it:

```bash
secret copy REGISTERED_NAME
```

Use `secret del REGISTERED_NAME` only for an explicit deletion request. Confirm
administration through the registered name and operation status, never the
value.

## Boundaries and failures

During adaptation, you may install the `secret` command and consolidate only
your own legacy MAINFRAME credential indexes into the central catalog. Do not
scan other agents' configuration roots. Preserve existing catalog entries and
never migrate content that appears to contain a secret value.

If the catalog has no suitable entry, report the exact missing credential or
catalog record. Do not invent a name, search unrelated projects or memory for a
value, or create persistent credential state without the explicit
administration request above.

Verify only whether the administration or consuming operation succeeded.
Return redacted evidence such as the registered name, operation status,
resource identity, or error class. Do not return request headers, environment
dumps, authenticated URLs, verbose traces, or unreviewed response bodies.

Hooks and native permission controls may enforce these boundaries, but their
absence does not weaken this skill's behavioral requirements.
