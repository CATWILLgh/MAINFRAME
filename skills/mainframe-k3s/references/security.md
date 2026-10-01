# Security and access

## Distinguish credentials from authority

The default admin kubeconfig at `/etc/rancher/k3s/k3s.yaml` grants unrestricted
cluster access. Keep it restricted to its authorized owner; do not make it
world-readable to fix client access. Use scoped identities and RBAC for people
and automation. Inspect only non-secret context/endpoint fields, never raw
kubeconfig contents. Copied admin kubeconfigs do not automatically receive the
certificate updates applied to the original on K3s startup.
Source: [cluster access](https://docs.k3s.io/cluster-access).

Protect join tokens, snapshot credentials and registry credentials as secrets.
Secure tokens provide CA-hash verification during joining; understand token type
before replacing it. Server-token rotation affects bootstrap encryption and
backup compatibility; retain the token associated with retained snapshots.
Source: [tokens](https://docs.k3s.io/cli/token).

## Apply controls with workload evidence

Assess host hardening, API access, workload privilege, namespace isolation and
audit needs. The bundled policy controller can enforce NetworkPolicies, but its
presence does not create isolation rules. Default-deny rollout must account for
DNS and required ingress/egress. Verify both permitted and prohibited traffic.
Source: [NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/).

Use the version-appropriate K3s hardening guide as a set of controls to evaluate,
not a universal config to paste. Pod Security enforcement can reject existing
workloads; audit/warn or a scoped rollout helps expose the impact. Kernel
protection settings require matching host setup. API audit policy/logging require
configuration and retention; avoid recording unnecessary sensitive content.
Document justified exceptions without calling the cluster CIS compliant merely
because a sample configuration was installed.
Source: [hardening](https://docs.k3s.io/security/hardening-guide).

Assess secrets encryption at rest. For enabling or rotating it on an existing
cluster, use the release-specific multi-server sequence and verify completion
on all servers; a flag alone does not prove old resources were rewritten.
Encryption at rest does not replace RBAC or protect secret values returned by
the API to an authorized identity.
Source: [secrets encryption](https://docs.k3s.io/security/secrets-encryption).

Check certificate status using `k3s certificate check` and supported output
options. Renewal on startup, leaf/key rotation and CA rotation are different
operations. Verify data-dir, version gates and the required stop/restart order;
do not delete TLS directories to fix expiration. Plan trust distribution and
client refresh for CA changes.
Source: [certificate lifecycle](https://docs.k3s.io/cli/certificate).
