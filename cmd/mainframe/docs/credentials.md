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

`mainframe credentials legacy-indexes` explicitly inspects the historical
credential locations. The Claude Code location has the historical role
`shared_original`: it was the original shared catalog location. The Codex,
OpenCode, and Antigravity locations have the role `adapter_copy`: they are
defensive checks for copies that may have been created later. These roles
describe locations and do not claim verified ancestry for any file found
there. A missing adapter copy is normal.

The command returns only release-defined locations, source roles, bounded
states, and read-only transfer readiness. It never returns file content,
content hashes, absolute paths, symlink targets, or raw filesystem errors.
Missing files and byte-identical current templates need no transfer. Safe
divergent files require manual transfer; unsafe files block readiness until
they receive attention. The command does not write, delete, or adopt an old
file, and always reports `migration_performed` as `false`.

`mainframe credentials legacy-preview` is a separate, explicitly partial
reference-discovery command. After direct invocation it reads the same bounded,
no-follow snapshot used for eligibility checks and extracts only named
`secret get NAME` uses from the historical shared original. It returns
validated section paths, exact reference names, occurrence counts, and whether
each name is compatible with the current catalog grammar. It does not return
raw lines or values.

Comments, quotations, fenced examples, malformed references, unscoped
references, and descriptive lines are counted but not returned. Divergent or
blocked adapter copies are listed as pending sources because they may contain
unique material. Therefore this preview remains a review aid: `coverage` is
`partial`, `migration_performed` and `apply_available` are `false`, and no old
file can be retired from this result.

`mainframe credentials legacy-plan` is the complete read-only planning surface
for the four classified historical locations. Unlike `legacy-preview`, it
parses every safe divergent source independently and keeps the component,
resource, source role, section path, occurrence count, and per-section
unmapped-line count attached to each proposal. Missing or current-template
sources need no transfer. One blocked source does not hide safe results from
the others, but it makes overall readiness and content accounting blocked.

The plan can carry exact compatible secret references into proposals and
report current value-free catalog uses. Instance ID, service, role, display
name, and purpose remain unresolved until a person reviews them. Legacy names
that do not fit the current grammar require an explicit rename. Shared
references and equivalent groups are relationships for review only: they never
merge or delete records automatically.

The release contract pins each classified historical resource to its exact
component, strategy, source path, target root, and target path. An additional
unclassified seed-if-absent resource ending in `.credentials-index` makes
planning fail closed. The response contains no raw lines, descriptions,
values, content hashes, filesystem paths, raw errors, digest, after-image, or
apply request. `migration_performed` and `apply_available` are always `false`.

`mainframe credentials legacy-review` checks a proposed transfer draft against
a freshly inspected `legacy-plan` and the current value-free catalog. The
strict JSON request carries the plan `release_id`, any proposed new instances,
and zero or one choice for each proposal. A choice either targets one exact
instance role or explicitly skips the proposal as `duplicate`, `obsolete`, or
`not_transferable`. A changed reference name requires
`rename_confirmed: true`.

Partial drafts are valid: omitted proposals are returned as `pending`. The
normalized response contains the complete value-free after-image and planned
catalog changes. A complete review with complete source accounting,
non-blocked content accounting, no pending choices, and at least one change
also returns
`apply_available: true`, an `apply_request`, and `expected_review`. Partial
content accounting may still apply recognized structured references, but keeps
`manual_content_review_required: true` and `retirement_ready: false`; the old
source remains pending and unchanged. Blocked accounting, pending choices, and
zero-change or skip-only reviews remain read-only. `migration_performed`
remains `false`.

Apply the returned request unchanged with:

```text
mainframe credentials legacy-apply --confirm <digest>
```

Apply rebuilds the plan and complete desired catalog from fresh state. The
digest binds the catalog review, normalized choices and accounting, and the
content and physical identity of every classified legacy source. A changed
catalog, release, source byte, mode, device, inode, or birth identity makes the
review stale. Source validation is the transaction's linearization point:
after it succeeds, later edits to historical files remain pending for a new
review and do not alter this catalog publication. Apply never writes, deletes,
or retires a historical source.

The terminal interface uses the same review model. Its transfer choices and
new instances exist only in the in-memory transfer draft and do not enter the
ordinary credential edit draft.

For example, this partial draft reuses one current catalog role:

```json
{
  "schema_version": 1,
  "kind": "mainframe-legacy-credential-transfer-draft",
  "release_id": "release-id-from-legacy-plan",
  "new_instances": [],
  "choices": [
    {
      "proposal": {
        "component_id": "claude-code",
        "resource_id": "claude-code.credentials-index",
        "source_role": "shared_original",
        "section_path": ["Catalog", "Home"],
        "reference_name": "CONTEXT7_HOME_KEY"
      },
      "expected_occurrences": 1,
      "action": "transfer",
      "target": {
        "instance_id": "context7-home",
        "role_id": "api-key"
      },
      "rename_confirmed": false
    }
  ]
}
```

Copy proposal identity fields and occurrence counts from the current
`legacy-plan`; do not reconstruct them. A `skip` choice uses an empty `target`
and one documented `skip_reason`.

Agents can create, edit, or delete instance metadata through:

```text
mainframe credentials instance review
mainframe credentials instance apply --confirm <digest>
```

Review reads a strict JSON request from standard input and returns a normalized
request plus a digest. Apply accepts only that normalized request and exact
digest, repeats the review against fresh state, and then uses the normal
transaction boundary. Deletion is explicit and never cascades into the secret
value store.

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

For a delete, set `operation` to `delete`, include only the existing
`instance_id`, and omit `instance`. Review returns the full desired catalog and
a change with `before` but no `after`. Deletion is rejected while another
instance requirement targets the record. It removes catalog metadata only; use
the separately reviewed secret-store retirement flow when the underlying value
is no longer shared or needed.

The review response contains `apply_request` and `expected_review`. Send the
returned `apply_request` unchanged on standard input to the apply command, and
pass `expected_review` as its `--confirm` argument. If state changed after
review, apply fails and the agent must review again.

Retire an unreferenced secret value through the separate reviewed flow:

```text
mainframe credentials secret-retire prepare <name>
mainframe credentials secret-retire apply --confirm <digest>
```

Preparation checks that the entry exists, that no credential-instance role
uses its exact `secret-env` name, and that none of the fixed MAINFRAME-managed
adapter ownership registries uses the exact name. Every registry is inspected;
an unsafe or unrecognized secret-bearing registry blocks retirement. The
secret value is never read into the response. Preparation may initialize the
store's opaque generation sidecar, so its capability effect is
`preparation-write`, not `read-only`.

The preparation response contains a value-free `apply_request` and
`expected_review`. Send that exact request on standard input. Apply acquires
the shared MAINFRAME transaction lock, repeats the catalog and managed-registry
checks from fresh state, verifies the digest and physical scope, and deletes
only if the secret-store generation still matches preparation. A new catalog
use, managed registry use, direct secret edit, changed path, or changed release
requires preparation again.

Retirement removes only the local store entry. It does not revoke the
provider-side credential and cannot remove copies already inherited by running
process environments. Perform those actions separately when they apply.
