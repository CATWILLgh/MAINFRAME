# Dokploy domains, ports, redirects, and TLS

Resolve the exact application or Compose service, internal listening port,
public hostname, DNS ownership, server address, routing mode, and certificate
method before changing ingress.

Verify the current domain schema and certificate workflow for the target
version. Confirm DNS records and externally relevant reachability before
requesting certificate issuance. Do not assume one ACME challenge type or
certificate provider applies to every configuration.

Treat the configured target as a container or service port unless the current
platform contract explicitly says otherwise. Avoid exposing a database,
administrative port, or internal service merely to make a health check pass.

Certificate issuance and routing reconciliation may be asynchronous. Verify:

- authoritative and client-visible DNS;
- expected HTTP and HTTPS routing;
- certificate subject, issuer, validity, and chain;
- redirect destination and absence of loops;
- application behavior through the public hostname.

Domain deletion, certificate replacement, extra published ports, and redirects
can cause outage or expand exposure. Apply [safety.md](safety.md) before those
changes.
