# Official source map

Reviewed 2026-10-09 against upstream stable documentation. The stable alias and
master schema move; neither establishes a particular installation's version.
Use the release matching the observed server, installed CLI help and the
server's Swagger UI before applying a flag or building a request.

| Question | Primary source |
| --- | --- |
| CLI authentication/environment | [Environment variables](https://argo-cd.readthedocs.io/en/stable/user-guide/environment-variables/) |
| CLI flags and operation support | [Command reference](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd/) |
| REST authorization and Swagger discovery | [API docs](https://argo-cd.readthedocs.io/en/stable/developer-guide/api-docs/) |
| Release-specific request/response schema | [Upstream Swagger](https://github.com/argoproj/argo-cd/blob/master/assets/swagger.json) at the matching release tag |
| Application namespace vs destination namespace | [Applications in any namespace](https://argo-cd.readthedocs.io/en/stable/operator-manual/app-any-namespace/) |
| Least-privilege actions/object identity | [RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/), [security](https://argo-cd.readthedocs.io/en/stable/operator-manual/security/) |
| Automation, pruning and rollback limits | [Automated sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/) |
| Resource recreation and data protection | [Sync options](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/) |
| Generated-app ownership | [ApplicationSet modification](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Controlling-Resource-Modification/), [deletion](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Application-Deletion/) |
| Ordering and partial-sync limits | [Phases and waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/), [selective sync](https://argo-cd.readthedocs.io/en/stable/user-guide/selective_sync/) |

No endpoint, credential name, cluster, repository, project or CLI release is
preselected by this skill. Examples describe syntax, not an installed target or
authority. Argo Workflows, Rollouts and Events are separate products; do not infer
their command/API contracts from Argo CD.
