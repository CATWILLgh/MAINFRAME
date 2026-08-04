# Domains, TLS, redirects, ports

Dokploy routes public traffic through Traefik. A domain attaches to an application or a Compose service and can auto-issue a Let's Encrypt certificate.

```bash
H=(-H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json")
```

## Attach a domain

`certificateType` is `letsencrypt` (auto HTTPS), `none` (HTTP only), or `custom` (bring your own cert). Only `host` is strictly required, but in practice you set the target and routing:

```bash
# application
curl -sS --fail-with-body "${H[@]}" -d '{
  "host":"app.example.com","applicationId":"<id>","port":3000,
  "https":true,"certificateType":"letsencrypt"}' "$DOKPLOY_URL/api/domain.create"
# compose service: target a service inside the stack
curl -sS --fail-with-body "${H[@]}" -d '{
  "host":"app.example.com","composeId":"<id>","serviceName":"web","port":80,
  "https":true,"certificateType":"letsencrypt"}' "$DOKPLOY_URL/api/domain.create"
```

`port` is the **container** port the service listens on; Traefik terminates TLS and proxies to it.

## Let's Encrypt preconditions

For `certificateType:letsencrypt` to succeed, the standard ACME HTTP-01 + Traefik requirements must hold (general Let's Encrypt/Traefik mechanics, not Dokploy-specific):
- A DNS `A`/`AAAA` record for `host` points to the server's public IP **before** creating the domain.
- Ports 80 and 443 on the server are reachable from the internet (ACME challenge + HTTPS).

Issuance is asynchronous; if it fails, check that DNS has propagated and the ports are open, then update the domain.

## Related routing

- **Redirects:** `redirects.create` / `redirects.delete` — HTTP→HTTPS or path redirects on a domain.
- **Extra published ports:** `port.create` / `port.delete` — expose additional TCP/UDP ports beyond the HTTP domain.
- **Custom certificates:** `certificates.*` — manage `custom` TLS certs (and `certificates.remove` to delete; see [safety.md](safety.md)).

## Inspect / change

- List/read with `GET /api/domain.byApplicationId?applicationId=<id>` (or `domain.byComposeId?composeId=<id>`).
- `domain.update` to change host/cert/port; `domain.delete` to remove the route.
