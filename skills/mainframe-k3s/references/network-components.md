# Network and packaged components

## Trace the actual path

Identify node interfaces, pod/service CIDRs, CNI backend, MTU, DNS and API endpoint
before changing firewall or routing. Avoid overlap with LAN, VPN and other
cluster networks. With the selected backend, permit only required peers:

| Purpose | Typical K3s port and scope |
| --- | --- |
| API/supervisor | TCP 6443 to servers from nodes and authorized clients |
| Embedded etcd | TCP 2379–2380 between servers |
| Flannel VXLAN | UDP 8472 between nodes; never expose publicly |
| Flannel WireGuard | UDP 51820; 51821 for IPv6, between nodes |
| Kubelet metrics/API | TCP 10250 between appropriate cluster nodes |

These are not a universal firewall recipe. Custom CNI, registry mirrors,
application ingress and optional components have their own needs. Check live
interfaces and the release-specific requirements.
Sources: [requirements](https://docs.k3s.io/installation/requirements),
[network options](https://docs.k3s.io/networking/basic-network-options).

## Respect component ownership

Inspect installed CoreDNS, Traefik, ServiceLB, metrics-server and local-storage
before introducing replacements. Traefik's LoadBalancer commonly occupies host
ports 80/443 through ServiceLB; investigate node selection and port conflicts.
Customize packaged Traefik with a matching HelmChartConfig and the bundled
chart's values, not edits to generated traefik.yaml. Disabling a packaged
component must be consistent across servers. Check the installed release before
changing Traefik/Gateway API CRDs; older versions have destructive disable cases.
Source: [network services](https://docs.k3s.io/networking/networking-services).

Files in the server manifests directory are live deployment inputs. Removing a
file does not delete its deployed resources. K3s does not synchronize user AddOn
files between servers: use one deliberate ownership/distribution strategy.
Source: [packaged components](https://docs.k3s.io/installation/packaged-components).

For alternative CNI, coordinate Flannel and built-in network-policy settings
with that CNI's official migration procedure. Disabling the built-in policy
controller leaves existing rules; cleanup is an explicit disruptive operation,
not permission to flush host iptables. Test intended allowed and denied paths.

Configure private-registry access on every image-pulling node, including
schedulable servers. Keep credentials out of output. A mirror can still fall
back to upstream; verify default-endpoint behavior for the installed release
before claiming isolation or air-gap support. Diagnose pulls on the failing
node rather than only the API client machine.
Source: [registry configuration](https://docs.k3s.io/installation/private-registry).
