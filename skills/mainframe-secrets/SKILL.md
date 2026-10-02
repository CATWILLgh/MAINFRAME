---
name: mainframe-secrets
description: Resolve credential identities, deliver secrets to a process, or administer entries through the MAINFRAME credential index and helper, without exposing values.
---

# Credential handling

Use the installed credential mechanism without bringing protected values into
model-visible commands or output.

## Resolve the credential

- Use existing native authentication or a credential reference already resolved
  in the current task when sufficient. Read `{{CREDENTIALS_INDEX}}` when a
  credential identity, delivery route, or catalog entry needs resolution.
- If a required catalog lookup is unresolved or unavailable, return the exact missing catalog
  configuration to your immediate caller. Do not search unrelated locations or
  initialize a replacement catalog.
- Treat the catalog as metadata only: service identities, addresses, credential
  names, access commands, and non-secret operational notes.
- Never read, search, print, summarize, diff, or archive the protected
  credential store.
- Do not use `mainframe-secret list` for routine discovery. Use the catalog.
- Do not infer authority to perform an external action merely because a
  credential exists.

## Deliver the value to a consumer

Prefer an already configured native mechanism such as an SSH agent, `gh`
authentication, a system credential service, or a consumer-owned credential
file.

When the consumer accepts an environment variable, prefer process-scoped
delivery:

```bash
mainframe-secret run REGISTERED_NAME -- consumer-command
```

This exposes only the requested registered names to that child process. Do not
load the complete store from shell startup files.

If the consumer requires a value in a specific input and no safer native,
environment, or stdin mechanism exists, nest `mainframe-secret get REGISTERED_NAME`
directly inside that single consumer invocation. Never run `mainframe-secret get` as a
standalone inspection command.

Never manually echo, log, serialize, retain, or place a value in a response,
prompt, ticket, URL, commit, patch, manifest, telemetry event, diagnostic trace,
model-authored shell variable, or temporary file. Avoid process arguments when
a safer delivery channel exists. Never weaken TLS, certificate, or SSH host-key
verification to make authentication succeed.

## Administer a credential

Treat an explicit instruction from your current recipient to register, update,
delete, or copy a credential for an identified service and purpose as authority
for that credential operation only. A registration request may include choosing
a clear, unique registered name and adding its non-secret catalog entry when
the recipient did not supply a name. Follow the catalog's naming and ownership
conventions: distinguish project-owned credentials from genuinely reusable
provider credentials. Do not add repeated confirmations, generic danger warnings,
or a refusal merely because the requested operation handles a credential. This
authority does not extend to an authenticated external action.

When the recipient says the value is in the clipboard, register or replace it
without inspecting the clipboard first:

```bash
mainframe-secret set REGISTERED_NAME --clipboard
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
mainframe-secret set REGISTERED_NAME --prompt
```

Never simulate protected input by placing the value in a tool call. If the
recipient has already supplied a value in the conversation, do not repeat or
quote it. Continue through a protected transfer route when one is available, or
state the single required clipboard or prompt action without abandoning
unrelated work.

On an explicit retrieval request, deliver the registered value directly to the
recipient's clipboard without reading or printing it:

```bash
mainframe-secret copy REGISTERED_NAME
```

Use `mainframe-secret del REGISTERED_NAME` only for an explicit deletion request. Confirm
administration through the registered name and operation status, never the
value.

## Boundaries and failures

If the operation requires the installed helper or protected transfer capability and it is
unavailable, return the exact missing capability. Credential handling does not
authorize installing the helper or migrating credential indexes. Preserve
existing catalog entries and never copy content that appears to contain a
secret value into the catalog.

If the catalog has no suitable entry and the task is to use an existing
credential, report the missing record; do not guess a secret name or search
unrelated projects or memory for a value. If the task explicitly authorizes
registering a new credential, choose its name from the catalog conventions,
register it through the helper, and add a metadata-only catalog entry so a
future agent can identify its owner, purpose, applicable projects/environments,
source, and rotation path without prior conversation context. Do not create
persistent credential state without that registration authority.

Verify only whether the administration or consuming operation succeeded.
Return redacted evidence such as the registered name, operation status,
resource identity, or error class. Do not return request headers, environment
dumps, authenticated URLs, verbose traces, or unreviewed response bodies.

Hooks and native permission controls may enforce these boundaries, but their
absence does not weaken this skill's behavioral requirements.
