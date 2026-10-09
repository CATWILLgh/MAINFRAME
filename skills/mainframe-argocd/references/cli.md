# CLI connection and bounded commands

Read for CLI operations. Check the installed `argocd ... --help` and the
matching release docs before relying on these examples. Do not install or
upgrade a client silently; prefer a client compatible with the observed server.

## Connection and credentials

1. `argocd version --client` does not contact a server. Obtain the server version
   only through the already authorized endpoint, for example `argocd version`
   with the established connection options. Do not run an unqualified command
   against whatever context happens to be active.
2. Use an explicit `--server` or verified `--argocd-context` and one consistent
   transport on every subsequent command. CLI `ARGOCD_SERVER` is a host/port
   without an `https://` prefix; REST uses a full HTTPS base URL. Check
   inherited `ARGOCD_OPTS` and non-secret target settings without dumping the
   environment or reading the token-bearing CLI configuration.
3. Use existing native authentication or process-scoped `ARGOCD_AUTH_TOKEN`
   delivery through the credential mechanism. Do not put tokens/passwords in
   arguments, command substitutions, traces, pasted requests or temporary files.
   Do not mint an admin token or perform login just to diagnose an app.
4. Use `--grpc-web` when the established proxy does not support native gRPC;
   verify its base-path requirements. It is not a TLS workaround. Keep certificate
   verification; use the known CA/server certificate when necessary. Do not
   improvise `--insecure` or `--plaintext` to resolve transport errors.

`--core` talks directly to Kubernetes; `--port-forward` creates a Kubernetes
transport. Neither is a fallback for an Argo CD permission failure. Use these
only when the assigned route includes the verified cluster and credentials.

Sources: [version](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_version/),
[environment](https://argo-cd.readthedocs.io/en/stable/user-guide/environment-variables/),
[ingress](https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/).

## Inspect one application

In these templates `ARGOCD_ENDPOINT`, `APP_NAMESPACE`, `APP_NAME` and
`APP_REVISION` are already resolved **non-secret** values. Supply the established
authentication and transport separately. Never execute the templates with
unresolved values. Pipe JSON through a narrow field projection before exposing
it to model context; inspect source settings privately where they may hold secrets.

```sh
argocd app get "$APP_NAME" --server "$ARGOCD_ENDPOINT" \
  --app-namespace "$APP_NAMESPACE" --timeout 30 --output json
argocd app diff "$APP_NAME" --server "$ARGOCD_ENDPOINT" \
  --app-namespace "$APP_NAMESPACE" --revision "$APP_REVISION"
```

`app get` returns observed status; `--refresh` requests reconciliation and
`--hard-refresh` also invalidates target-manifest cache. With automation enabled,
refresh can expose drift to reconciliation; it is not a pause or passive read.
Do not use hard-refresh in an unbounded loop.

Diff code 1 normally means differences; it does not mean the server failed.
Check the installed version's error and configurable diff codes rather than
retrying every nonzero result or swallowing it with `|| true`. Kubernetes Secrets
are excluded from this diff, but other resources can still embed secrets.
`KUBECTL_EXTERNAL_DIFF` selects an external executable: retain only a known tool.

Sources: [get](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_get/),
[diff](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_diff/).

## Sync and wait after authorization

For a reviewed **single-source** app with a resolved immutable Git revision,
the minimal non-pruning example is:

```sh
argocd app sync "$APP_NAME" --server "$ARGOCD_ENDPOINT" \
  --app-namespace "$APP_NAMESPACE" --revision "$APP_REVISION" --timeout 60
argocd app wait "$APP_NAME" --server "$ARGOCD_ENDPOINT" \
  --app-namespace "$APP_NAMESPACE" --operation --sync --health --timeout 60
```

Reinspect the revision and operation after wait; a different automated operation
can satisfy status flags. Continue bounded observation when deployment needs more
time. A wait timeout does not terminate server work. `--async` acknowledges
submission, not completion. Do not add retry flags or `--retry-refresh` blindly.

`--dry-run` previews apply, not hook execution or a rollback rehearsal. Multi-source
sync needs explicit corresponding `--revisions` and `--source-positions` (1-based)
or supported `--source-names`; do not apply the single-source template to it.
Avoid wildcard/label/project selectors unless the entire expanded set is authorized.
Check [operations](operations.md) before selective sync or risky sync options.

Sources: [sync](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_sync/),
[wait](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_wait/).
