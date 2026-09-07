# Adapt credentials support

Use this guide for the single `shared.credentials` inventory entry and for the
central non-secret index it supports.

## Canonical boundary

Only [shared/credentials/secret](../../../shared/credentials/secret) is global
payload. Run [install.sh](../../../shared/credentials/install.sh) from the
repository; do not copy it globally. The adjacent index template, ignored local
index, and tests remain repository support. Never copy the complete directory.

The centralized index is `shared/credentials/credentials-index.md`. It contains
service descriptions, addresses, credential references, access commands, and
notes, never secret values. Verify it is ignored before creating it from the
template.

## Reconcile the helper

Inspect the helper and installer before execution. Resolve the current global
`secret` command identity without printing its body from a protected location.

- Preserve an existing compatible command.
- Install the canonical helper only when absent or when the installer positively
  identifies a replaceable legacy MAINFRAME helper.
- Never overwrite an unrelated command with the same name.
- Never load a credential store through a shell startup file.

The preferred human path registers clipboard content with `secret set NAME
--clipboard`. Protected interactive `--prompt` input is the fallback. `secret
copy NAME` returns a requested value to the user's clipboard. Process-scoped or
direct nested delivery passes a value straight to its consumer. These paths
must not place values in command arguments or print them.

## Migrate only this product's old index

Search only the installed product's already resolved configuration roots for an
index from its own earlier MAINFRAME installation. Merge non-secret metadata
into the central index without overwriting an existing record. Preserve both
sides of a semantic conflict with their origins identified.

Never search other products, repositories, archives, backups, or the home
directory broadly. Never migrate a suspected value. Remove only a positively
identified obsolete index owned by this same product after the merged index and
helper are verified.

## Verify

Use the helper's repository tests first. Then prove the resolved global command
supports protected registration and clipboard retrieval without exposing the
test value in arguments, stdout, stderr, state, shell history, or logs. Use a
disposable synthetic value and remove it through the helper afterward.

Do not read, print, diff, summarize, archive, or place a protected credential
store in model context.
