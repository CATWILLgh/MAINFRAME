---
name: mainframe-argocd
description: Plan, operate, or troubleshoot Argo CD GitOps through its CLI or REST API, including Application/ApplicationSet ownership, sync, drift, rollout verification, rollback and deletion. Not Argo Workflows or application implementation.
---

# Operate Argo CD against an explicit target

Establish the requested result and reuse its existing authority. This method
does not grant permission to deploy, prune, delete, change access, or repair a
cluster. A read-only diagnosis remains read-only. Stop only an action whose
target, authority, or recovery boundary is missing; continue useful inspection.

## Identify what will actually change

Before a remote operation, resolve:

- Argo CD API server, environment, observed client/server versions and transport;
- Application name **and its metadata namespace**, AppProject, destination
  cluster identity and workload namespace; these namespaces are different;
- source repository/path or chart, requested revision, and all sources/overrides
  for a multi-source Application;
- configuration owner: Git, parent Application, ApplicationSet or explicitly
  unmanaged Application; current automated sync, self-heal, prune, sync options
  and pending operation.

A CLI on this machine, localhost, a port-forward or the in-cluster destination
alias does not identify a disposable cluster. Resolve the remote owner instead
of accepting a familiar name or the active CLI/kubeconfig context as proof.
If the environment is uncertain, treat it as shared/non-disposable and resolve
the ambiguity before writes. Use the same established identity for CLI and API.

## Load the relevant reference

| Decision | Read |
| --- | --- |
| Connect, authenticate, inspect an app or invoke bounded CLI commands | [CLI](references/cli.md) |
| Build authenticated REST requests, interpret errors or handle uncertain outcomes | [API](references/api.md) |
| Configure GitOps, sync, diagnose drift, recover or remove an app | [Operations](references/operations.md) |
| A version-sensitive flag, schema or behavior | [Official sources](references/sources.md), then the target release documentation/help |

Use `mainframe-secrets` for credential delivery, `mainframe-curl-requests` for
raw curl transport, and `mainframe-infrastructure` for deployment coordination.
Use `mainframe-k3s` when the problem actually concerns the underlying K3s cluster.
Do not preload unrelated references or replace the project's release runbook.

## Separate inspection from deployment

Inspect only the app and fields needed. Do not dump CLI config, tokens,
repository/cluster credentials, Secret manifests, full parameter values or
unreviewed logs. Generated manifests and diffs may also contain sensitive data.

Before a change, make its scope reviewable: exact app/revision/resources,
controller ownership, diff, hooks and migrations, deletion/data effects,
required access, recovery route and acceptance condition. Git edits, merge or
push to a watched source can deploy automatically; local editing authority does
not by itself authorize that release. Reuse explicit release authority without
asking again for an unchanged bounded operation.

Prefer correcting the declarative owner. Do not patch a generated child merely
because the API accepts it. Never widen selection to all apps, use force/replace,
skip checks, enable prune or remove a finalizer as generic error recovery.
Preview is evidence, not permission or proof that real hooks/data effects are safe.

## Prove the requested result

After an authorized write, observe the same operation and resolved revision(s),
terminal result, sync and health independently. Check relevant live resources,
images and application behavior. `Synced`, `Healthy`, HTTP 200, or a completed
CLI process alone does not establish the intended release.

A timeout/disconnection leaves a write outcome uncertain. Read the app's
operation state and live effects before considering another write; do not
blindly repeat sync, migration hooks, delete or rollback. A failed multi-resource
sync can already have changed some resources.

Report the exact target, action taken, revision(s), observed evidence and any
remaining gap. For planning or diagnosis, say that no release was performed.
