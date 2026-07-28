# Local releases

MAINFRAME keeps complete releases in a versioned local store and activates the
`mainframe` command against one exact stored version. This operation does not
select, remove, or rewrite adapter configurations.

Review a local release before importing it:

```sh
printf '%s\n' '{
  "schema_version": 1,
  "kind": "mainframe-release-change",
  "operation": "import-and-activate",
  "source_path": "/absolute/path/to/release"
}' | mainframe release review
```

To switch or roll back to a version already in the store, use
`activate-cached` with the exact `release_id` and `index_sha256` returned by an
earlier review.

Review is read-only. It returns at most one launcher operation, an exact apply
request, and a `sha256:` confirmation when the change is applicable. Apply the
returned request unchanged:

```sh
mainframe release apply --confirm 'sha256:...' < apply-request.json
```

The confirmation is a local review digest, not a publisher signature. Local
release hashes verify that content has not changed; publisher authentication
is a separate requirement for future network delivery.

Apply first rechecks the source, exact release identity, transaction state, and
current launcher without writing. Only a matching confirmation permits import
and one recoverable activation transaction. A failed activation may leave a
validated version in the local store, but it does not leave the launcher or
ownership record half-switched.

If review reports `recovery_required`, open `mainframe` once to complete the
existing recovery before reviewing the release again.
