# Upgrades and troubleshooting

## Upgrade a bounded target

Check existing and target K3s/Kubernetes versions, release notes, packaged chart
changes, deprecated APIs and CNI/CSI compatibility. Do not skip Kubernetes minor
versions. Upgrade servers one at a time before agents, with health/quorum checks
between steps. An automatic upgrade controller does not validate every version
transition. Preserve service arguments/environment and config when rerunning
the installer. It restarts K3s but does not automatically cordon/drain nodes.
Choose draining from actual workload disruption needs rather than treating
every service restart as a full eviction.
Source: [manual upgrades](https://docs.k3s.io/upgrades/manual),
[version skew](https://kubernetes.io/releases/version-skew-policy/).

Before eviction, inspect replica capacity, PodDisruptionBudgets, DaemonSets,
unmanaged pods, local PVs and emptyDir data. Do not bypass a blocked drain with
force, disabled eviction or delete-emptydir-data unless that specific loss or
outage is authorized. A singleton or node-bound stateful workload may require a
maintenance window or another recovery plan. Uncordon after the intended checks.
Source: [safe drain](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/).

## Diagnose from the failing surface

Start with a bounded read-only observation on the verified cluster. Specify
context/namespace rather than changing global kubectl context implicitly.
Useful initial queries, selected for the symptom:

```sh
kubectl --context "$K3S_CONTEXT" --request-timeout="$K3S_API_TIMEOUT" get nodes -o wide
kubectl --context "$K3S_CONTEXT" --request-timeout="$K3S_API_TIMEOUT" -n "$K3S_NAMESPACE" get pods -o wide
kubectl --context "$K3S_CONTEXT" --request-timeout="$K3S_API_TIMEOUT" -n "$K3S_NAMESPACE" get events --sort-by=.metadata.creationTimestamp
```

Define context/namespace from verified target metadata and a finite timeout
from the task's observation budget (a duration such as `10s`); these contain no secrets.
Use timeouts and bounded output where supported. Events, pod descriptions and
logs can contain sensitive application values: inspect only needed fields and
redact before sharing. Do not dump Secrets, raw kubeconfigs or service env files.

| Symptom | Next evidence |
| --- | --- |
| API unavailable / server join rejected | Endpoint/TLS, service logs, critical config match, datastore/quorum, disk and clock |
| Node NotReady | Node conditions, kubelet/runtime logs, pressure, CNI/interface/MTU |
| Pending pod / PVC | Scheduler events, requests/capacity/taints, PV affinity and storage provisioner |
| Image pull failure | Failing node's registry route/auth/CA and containerd logs |
| DNS / ingress failure | CoreDNS and endpoints, Service/EndpointSlice, CNI policy, ingress controller/ServiceLB and actual client route |
| CrashLoop | Bounded current/previous container logs, probes, configuration and resource pressure |

Use the actual runtime. K3s bundles containerd and `k3s crictl`/`k3s ctr`;
Docker CLI evidence is not a substitute unless Docker is explicitly configured.
Host journal access belongs on the verified host, not automatically your laptop.
Sources: [CLI tools](https://docs.k3s.io/cli),
[advanced configuration](https://docs.k3s.io/advanced).

For ingress, inspect the named Ingress's class and backend, its Service selector
and ports, and EndpointSlices selected by `kubernetes.io/service-name`. Compare
endpoint readiness with the serving controller's bounded logs. Separately check
controller LoadBalancer Services and ServiceLB pod host ports, placement and
scheduler events. Empty upstreams and a host-port collision require different
repairs; identify which controller the actual client reached before changing
exposure. Preserve its Host header and TLS/SNI when verifying the route.
Source: [network services](https://docs.k3s.io/networking/networking-services).

Make one evidence-supported change at a time, then repeat the observation that
failed. Do not install a monitoring stack just to investigate one incident.
For ongoing operations, cover disk/inodes, datastore latency/quorum, node
pressure, certificates, backup success and the actual workload's availability.
