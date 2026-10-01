---
name: mainframe-k3s
description: Design, install, troubleshoot, secure, upgrade, or recover K3s clusters and their networking or storage. Excludes unrelated Kubernetes distributions and application-only changes.
---

# Operate K3s with evidence

Establish the requested result, exact cluster and environment, current K3s
versions, datastore, node roles, and relevant workload before choosing an
operation. Reuse verified project context and caller authority. A local
kubeconfig, loopback address, SSH tunnel, or local CLI does not establish a local
or disposable cluster. Verify the API endpoint and node/host identities without
printing credentials. If a missing fact changes the safe decision, resolve it
rather than assuming a default installation.

Use `mainframe-infrastructure` for broader infrastructure coordination and its
project map; keep K3s-specific decisions here. Use `mainframe-secrets` when
credentials are required. This skill does not grant cluster write authority.

## Load the relevant method

| Decision | Read |
| --- | --- |
| Choose topology, provision nodes, join servers or preserve configuration | [Topology and installation](references/topology-installation.md) |
| CNI, DNS, ingress, ServiceLB, registry or connectivity failure | [Network and components](references/network-components.md) |
| Access control, hardening, certificates or encryption | [Security](references/security.md) |
| Persistent data, backup, disaster recovery or rollback | [Data and recovery](references/data-recovery.md) |
| Upgrade, drain, capacity or incident investigation | [Operations](references/operations.md) |
| A flag, version gate, compatibility decision or missing detail | [Official source map](references/sources.md), then the applicable live documentation |

Load only references needed by the current decision. Check version-sensitive
syntax against the installed binary's help and official documentation for that
release. Do not treat a documentation example, latest channel, or remembered
component version as the target's actual configuration.

## Make the result reviewable

For a design, explain the selected topology, failure tolerance, data durability,
resource/network assumptions, and alternatives that materially change cost or
risk. For a change, identify its configuration owner, exact targets, expected
impact, recovery path and bounded verification. Preserve unrelated settings and
existing GitOps or configuration-management ownership.

Do the authorized operation and relevant verification. Stop only the action
whose target, authority, or necessary recovery boundary is missing; continue
useful independent work. Do not use uninstall, killall, cluster reset, forced
eviction, or data-directory deletion as generic troubleshooting.

Prove the requested outcome at the right level: API readiness, node health,
DNS/network reachability, ingress and application behavior, and persistent data
are different observations. Choose only the checks relevant to the change.
Report observed evidence, remaining uncertainty and the exact next action when
blocked. A snapshot listing or Ready node alone does not prove recoverability or
application availability.
