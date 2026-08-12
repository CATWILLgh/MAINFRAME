# Authentication and sessions

Preserve the project's security architecture: browser OAuth/OIDC client, bearer-token resource server, server-side BFF session, service credential, or a deliberate combination. Establish the provider, trust boundary, installed Authlib or JWT version, and token or cookie owner before changing it.

## OAuth and OpenID Connect

- Use authorization code flow for browser sign-in and PKCE where the client type requires it. Validate redirect targets against an allowlist.
- Bind authorization response to the initiating browser through `state`; validate OIDC `nonce` when an ID token participates in login.
- Validate token signature and expected issuer, audience, algorithm, expiry, and token purpose. A decoded JWT is not yet a trusted token.
- Use provider metadata and JWKS through the established client. Bound network timeouts and cache keys with a safe refresh path; do not fetch discovery or keys on every request.
- Separate transient provider failure from rejected credentials and malformed provider responses. Do not turn every failure into `401`.

## Sessions and cookies

- Keep access and refresh tokens out of browser-readable storage when the architecture uses a BFF. Store only the minimum session reference in a cookie when possible.
- Use `Secure`, `HttpOnly`, an appropriate `SameSite`, narrow domain and path, deliberate lifetime, and CSRF protection for cookie-authenticated state changes.
- Make refresh rotation, replay handling, logout, revocation, session eviction, and provider outage behavior explicit.
- A Redis-backed session has a correctness decision: define fail-open or fail-closed behavior per operation and test expiry, missing payload, stale indexes, and temporary unavailability.

## Authorization

Map external identity to a current local subject deliberately. Authorize each operation and resource using server-owned roles, capabilities, tenant membership, or policy. Provider claims are input to that decision, not a substitute for resource ownership checks.

## Sources

- Authlib Flask OAuth/OIDC client — https://docs.authlib.org/en/latest/oauth2/client/web/flask.html
- OpenID Connect Core — https://openid.net/specs/openid-connect-core-1_0.html
- OAuth 2.0 Security Best Current Practice — https://www.rfc-editor.org/rfc/rfc9700
- OWASP session management — https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
