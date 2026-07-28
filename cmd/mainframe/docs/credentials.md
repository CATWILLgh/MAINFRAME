# Credentials

MAINFRAME separates three things:

- a shipped service definition, such as Context7;
- a user-owned instance, such as a work or home server;
- a secret value owned by the configured secret backend.

An instance stores a short name, purpose, service, roles, and a reference to a
secret name. It never stores the secret value. Several instances may reference
the same secret name, and one instance may be selected by several adapters.

The terminal interface supports masked, paste-capable secret entry. The value
is sent directly to the secret helper and is not placed in command arguments,
preview text, logs, journals, diagnostics, or the credential catalog.

When keyed Context7 is applied to OpenCode, the selected reference is resolved
only after final confirmation. MAINFRAME writes the value to a private
OpenCode-only file and places a `{file:...}` reference in `opencode.json`.
Switching to keyless mode or removing Context7 removes that managed private
file. The catalog continues to own only metadata and references.

`mainframe credentials` prints the value-free catalog as versioned JSON.
`mainframe credentials uses <name>` lists instance roles that reference one
secret name. It does not read that secret.

`mainframe credentials legacy-indexes` explicitly inspects the four old
adapter-local Markdown indexes. It returns only their release-defined
locations, bounded states, and read-only transfer readiness. It never returns
file content, content hashes, absolute paths, symlink targets, or raw
filesystem errors. Missing files and byte-identical current templates need no
transfer. Safe divergent files require manual transfer; unsafe files block
readiness until they receive attention. The command does not write, delete, or
adopt an old file, and always reports `migration_performed` as `false`.

Agents can create or edit instance metadata through:

```text
mainframe credentials instance review
mainframe credentials instance apply --confirm <digest>
```

Review reads a strict JSON request from standard input and returns a normalized
request plus a digest. Apply accepts only that normalized request and exact
digest, repeats the review against fresh state, and then uses the normal
transaction boundary. Create and edit do not imply deletion.

A create request has this shape:

```json
{
  "schema_version": 1,
  "kind": "mainframe-credential-instance-change",
  "operation": "create",
  "instance": {
    "id": "context7-home",
    "service_id": "context7",
    "name": "Home",
    "purpose": "Personal research",
    "credentials": [
      {
        "role_id": "api-key",
        "secret": {
          "backend": "secret-env",
          "name": "CONTEXT7_SHARED_KEY"
        }
      }
    ]
  }
}
```

For an edit, set `operation` to `edit`, add `instance_id`, and keep it equal to
`instance.id`. Obtain valid service and role IDs from `mainframe credentials`;
do not invent them.

The review response contains `apply_request` and `expected_review`. Send the
returned `apply_request` unchanged on standard input to the apply command, and
pass `expected_review` as its `--confirm` argument. If state changed after
review, apply fails and the agent must review again.
