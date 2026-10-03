# Settings and API boundary

Adapt routes and persistence to the app; these are contracts, not mandated paths.

| Operation | Required behavior |
| --- | --- |
| Public provider summary | Enabled state, display label and same-origin login start URL only; no secrets, mappings, internal endpoints or raw error details |
| Start / callback | Browser navigation with transaction validation and app-session issuance; safe redirect on failure, no raw exception page |
| Admin settings read | Explicit admin authorization; non-secret configuration, secret-present indicator, server-derived callback URI and revision |
| Admin settings save | Server-side validation, CSRF/origin protection, concurrency revision check, audited change and atomic application |
| Admin draft test | Same authorization and outbound policy as save; bounded diagnostic without persistence, enablement or real user creation |

Fields: enabled, display name, realm issuer URL, client ID, client type,
groups-claim selector, default access policy and ordered group-to-role mappings.
Show a client-secret update field only for a backend confidential client. Use
concrete role IDs from the project, not a copied example application's role list.

GET returns `hasClientSecret`, never the secret or its suffix. Distinguish secret
operations explicitly: keep, replace with a nonempty value, and clear. A visual
mask is a placeholder, not a value sent back to storage. Never interpret arbitrary
bullet characters as a secret-preservation protocol. Clearing a required secret
must disable/reject an otherwise enabled confidential configuration, visibly.
Encrypt stored secrets or use the established protected secret reference. Omit
credentials, tokens and sensitive profiles from logs, audit diffs and responses.

Use an authoritative config store with revisions and consistent invalidation
across replicas. Environment values may seed a missing setting once, but must
not overwrite a saved disabled/cleared configuration. Do not update per-process
state before a failed persistence attempt. Realm/client changes must not rebind
existing external identities. Apply a documented reauthentication policy.

Derive the callback URI from a configured, trusted external origin and route.
Do not trust arbitrary Host/X-Forwarded-* headers or allow a user-controlled return
URL. Register the exact callback URI in Keycloak, without broad wildcards. Public
issuer identity remains stable behind proxies; an internal transport route is
not permission to replace issuer validation with a private hostname.

## Outbound discovery and diagnostics

An editable realm URL is an outbound request capability. Restrict target schemes,
hosts, ports, resolved destinations and redirects according to the deployment's
explicit IAM policy; reject URL userinfo and unexpected query/fragment components.
Protect metadata, loopback and unrelated internal services. Enterprise IAM may
be private: authorize the specific private destination instead of permitting all
private addresses or unconditionally banning them. Apply the same controls to
discovery endpoints, JWKS, token and UserInfo requests. Never send the client
secret to an unvalidated discovered endpoint. Keep TLS verification enabled and
bound time, response size, redirect count and diagnostic concurrency.

Test the submitted draft plus the explicitly retained/replaced secret against
that policy. Return separate results such as discovery, issuer match, endpoint
reachability, client authentication and interactive login, each with
passed/failed/not-tested. Mark old results stale when the form changes.

Discovery success proves neither credentials nor usable login. Do not enable
service accounts just to test SSO. Client-credentials success, where separately
configured, proves only that grant. An `invalid_grant` from an intentionally bad
authorization code is not sufficient proof of valid client authentication.
When a safe credential check is unavailable, say not-tested and complete an
actual authorization-code login in the designated test environment. Expose
sanitized error categories rather than raw provider payloads.
