# Official source map

Research baseline: 2026-10-01. The linked documentation evolves; this date is
not proof for a different installed release. Follow the relevant version gates,
release notes and binary help before using flags or changing components. The
procedures in this skill are distilled operational guidance; the links below
own product syntax and compatibility facts.

| Question | Primary source |
| --- | --- |
| Hardware, Linux and firewall | [Requirements](https://docs.k3s.io/installation/requirements) |
| Config precedence and persistence | [Configuration](https://docs.k3s.io/installation/configuration), [server](https://docs.k3s.io/cli/server), [agent](https://docs.k3s.io/cli/agent) |
| Datastore choice and HA | [Datastore](https://docs.k3s.io/datastore), [embedded HA](https://docs.k3s.io/datastore/ha-embedded), [external HA](https://docs.k3s.io/datastore/ha) |
| CNI and bundled networking | [Network options](https://docs.k3s.io/networking/basic-network-options), [services](https://docs.k3s.io/networking/networking-services) |
| AddOns and chart ownership | [Packaged components](https://docs.k3s.io/installation/packaged-components), [Helm](https://docs.k3s.io/add-ons/helm) |
| Images and disconnected nodes | [Registries](https://docs.k3s.io/installation/private-registry), [air-gap](https://docs.k3s.io/installation/airgap) |
| Privileges, tokens and hardening | [Access](https://docs.k3s.io/cluster-access), [token](https://docs.k3s.io/cli/token), [CIS guide](https://docs.k3s.io/security/hardening-guide) |
| Encryption and certificates | [Encryption](https://docs.k3s.io/security/secrets-encryption), [certificates](https://docs.k3s.io/cli/certificate) |
| Storage and recovery | [Volumes](https://docs.k3s.io/add-ons/storage), [backup](https://docs.k3s.io/datastore/backup-restore), [snapshots](https://docs.k3s.io/cli/etcd-snapshot) |
| Upgrade and rollback | [Manual](https://docs.k3s.io/upgrades/manual), [automated](https://docs.k3s.io/upgrades/automated), [rollback](https://docs.k3s.io/upgrades/roll-back), [releases](https://github.com/k3s-io/k3s/releases) |
| Runtime investigation | [CLI](https://docs.k3s.io/cli), [advanced](https://docs.k3s.io/advanced) |
| Kubernetes compatibility and eviction | [Skew](https://kubernetes.io/releases/version-skew-policy/), [drain](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/) |
| Kubernetes data and isolation semantics | [PV](https://kubernetes.io/docs/concepts/storage/persistent-volumes/), [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/) |

For a third-party CNI, CSI, backup agent or ingress replacement, add that
component's official version-specific evidence to the current task. Do not
inherit compatibility from K3s supporting a different release of the component.
