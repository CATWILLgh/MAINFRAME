# Topology and installation

## Select the failure model

Use a single server with SQLite when its outage and recovery time are acceptable.
For embedded-etcd HA, choose at least three servers with an odd member count;
three tolerate one member loss. Additional agents do not increase etcd quorum.
Distribute servers across suitable failure domains with reliable low-latency
connectivity and fast durable disks. HA does not replicate application volumes.
An external datastore adds its own availability, TLS, capacity and backup owner;
choose it for a concrete operational requirement, not simply the word production.

Sources: [datastores](https://docs.k3s.io/datastore),
[embedded etcd](https://docs.k3s.io/datastore/ha-embedded).

Before provisioning, check Linux/kernel/cgroup support, unique node identities,
clock synchronization, disk space/latency, CPU and memory headroom for workloads,
node addressing and pod/service CIDR conflicts. Minimum advertised resources
exclude application demand. Prefer SSD-backed datastore storage. Keep firewall
rules scoped to the selected network rather than disabling the host firewall.
Source: [requirements](https://docs.k3s.io/installation/requirements).

## Keep configuration reproducible

Resolve the desired release from the supported upgrade path and release notes;
use an explicit version for a reproducible change, without imposing a permanent
repository-wide pin. Inspect existing service arguments, environment and config
through a secret-safe allowlist. Record the non-secret effective settings.

Prefer persistent K3s configuration over a growing install command. By default
K3s reads `/etc/rancher/k3s/config.yaml` and alphabetically ordered
`config.yaml.d/*.yaml`. CLI options override file settings, including replacement
of list values. Later files replace values unless the documented `+` append
syntax is maintained. Rerunning the install script without the original
arguments/environment can lose those settings; it does not own config.yaml.

Separate initial cluster creation from joining existing servers. Match critical
settings on all servers, including cluster/service CIDRs and component disable
flags. Verify actual datastore state before relying on `cluster-init` or server
flags: an existing etcd datastore changes initialization behavior. For a stable
API/registration endpoint, configure its certificate SAN and verify routing.

Sources: [configuration](https://docs.k3s.io/installation/configuration),
[server flags](https://docs.k3s.io/cli/server).

Review the installer or managed provisioning artifact before executing it under
the authorized target account. Do not turn an installation request into an
unreviewed host reset. Confirm membership, critical config consistency and the
intended workload path after joining nodes.
