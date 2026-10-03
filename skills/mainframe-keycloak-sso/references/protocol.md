# Protocol, identities and authorization

## Authentication and session handoff

For an app with a trusted backend, prefer authorization code + PKCE S256 with
server-side token exchange and the existing server-managed session. Keep the
confidential client's secret and refresh tokens server-side. For a public SPA,
use a public client and a maintained browser OIDC library; do not expose a
confidential secret or automatically replace the app's session design.

Create cryptographically random state, nonce and PKCE verifier for each login.
Bind them to the initiating browser, expected issuer/client, exact callback URI,
configuration revision, bounded expiry and an allowlisted return path. Validate
and atomically consume the transaction once. Support concurrent tabs and multiple
instances with a shared transaction store, or an authenticated/encrypted cookie
with a demonstrated replay/consumption mechanism. Unsigned state/verifier cookies
and per-process state without routing guarantees are not interchangeable solutions.
Set Secure, HttpOnly and an appropriate SameSite policy for the actual callback
response mode; test cross-site behavior rather than assuming every mode uses GET.

Require an ID token and validate it with a maintained library: allowed signature
algorithms and keys, exact expected issuer, audience, authorized-party rules for
multiple audiences, expiry, issued-at and nonce. Reject missing required claims,
unknown algorithms and token-provided arbitrary key URLs. Bound JWKS/discovery
fetches and cache lifetime; support controlled key rotation and unknown-kid
refresh without unbounded retries. If using UserInfo, require its subject to
match the validated ID token before consuming profile or group claims.

Use the app's session issuance/rotation path; regenerate the session after login.
Do not return access or refresh tokens in query strings or URL fragments, or
introduce refresh-token localStorage as a shortcut. A redirect returns to a
fixed safe app route; if architecture requires a separate handoff, exchange a
short-lived, single-use, browser-bound opaque code server-side. Strip callback
parameters before analytics or third-party resources can observe them. Protect
cookie-authenticated mutations with the app's CSRF/origin defenses.

## Account identity and mapping

Store external identity by exact `(issuer, subject)` with a uniqueness constraint,
linked to a local user. Username and email are mutable profile fields: neither
is sufficient proof to bind an existing account, even if email is verified.
Require authenticated linking with reauthentication or a separately authorized,
audited administrative migration. Deny conflicting links; concurrent first
logins must not create duplicate users or partially linked identities.

For JIT provisioning, check the mapped role and access policy before creating
an active account. Preserve local deactivation and existing link ownership.
Never reactivate a disabled local user from a successful IAM authentication.
Recompute IAM-managed roles on login and at the app's defined revalidation point.
Preserve profile provenance; linking does not silently change account origin.

Choose one configured authoritative group source from validated claims. Do not
union stale/conflicting sources to produce broader access. Missing, malformed or
unmapped groups deny by default. Validate mapped roles against the application's
real assignable role set on the server, including privilege-grant authority.

Prefer exact, case-sensitive full group paths. Do not lower-case, discard parent
paths or match leaf names automatically: `/finance/admin` and `/support/admin`
need not grant the same access. If a legacy policy needs normalization, document
its collision rules and reject ambiguity. For a single-role app, use an explicit
ordered mapping with visible first-match priority; multi-role apps retain their
existing policy instead of inventing an implicit privilege union.

## Recovery and session lifetime

Keep a separately managed, tested local break-glass route when the app has one.
A password hash plus an admin role is not sufficient evidence to exempt an
SSO-linked account from role revocation. Never auto-link an IAM identity to a
recovery admin by username. Preserve recovery access without laundering its
privileges into ordinary SSO sessions.

Specify what happens to existing sessions when SSO is disabled, a mapping changes,
a user is removed from IAM or a local account is deactivated. Updating on next
login alone is not immediate revocation. Use the established bounded session
TTL/revalidation or supported logout/revocation integration; do not promise
instant offboarding without proving it. Distinguish local app logout, provider
logout and logout across other applications. Validate any logout token using the
library's dedicated contract and protect against replay when that mode is used.
