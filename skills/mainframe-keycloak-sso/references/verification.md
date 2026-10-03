# Verification boundaries

Use the project's testing strategy; keep the ordinary local loop in-process.
Use a fake OIDC provider and isolated local PostgreSQL only when relational
semantics matter. Real Keycloak/container and browser integration belong in CI
or an explicitly authorized test environment; never probe production by default.

| Guarantee | Evidence to obtain |
| --- | --- |
| Login correlation | Valid code flow; wrong/missing state or nonce, expired/replayed transaction, wrong PKCE, concurrent tabs and callback on another replica |
| Token trust | Invalid signature/algorithm, missing ID token, wrong/case-altered issuer, audience/azp failures, expired token, UserInfo subject mismatch, key rotation |
| Identity safety | Same username/different subject cannot link; same subject/different issuer stays separate; explicit linking checks, concurrent JIT, disabled local user |
| Roles | No/malformed/unmapped groups deny; full-path/case collisions; explicit precedence; invalid role rejected; no silent privilege union or recovery-admin linking |
| Session lifecycle | Session regeneration, refresh handling, replay, logout and defined offboarding/role-change delay; no credentials in redirects or logs |
| Settings | Unauthorized/CSRF requests rejected; keep/replace/clear secret; validation, stale revision, failed save, persisted disable and replica consistency |
| Diagnostics | Draft does not persist; blocked targets/redirects, timeout, bad TLS, oversized discovery, issuer mismatch; partial result never reported as full login success |
| UX | All states in the interface contract, actual controls/persistence, local login preserved, inaccessible admin routes, localized callback errors |

A fake provider should assert PKCE challenge/verifier correspondence and nonce,
not merely that fields are nonempty. Use synthetic keys/accounts; do not commit
live realm exports, cookies, secrets, tokens or user profiles.

In the authorized Keycloak test environment, verify client authentication type,
standard authorization-code flow, PKCE configuration, exact redirect URIs and the
group mapper/claim source against the installed version's docs. Do not enable
password grants or service accounts just to make a diagnostic pass. Request only
necessary scopes and expose group membership only to the client that needs it.

Perform an actual browser login, denied unmapped login, configured group change,
local deactivation and recovery login. Separate login-time updates from the
verified deadline for existing-session revocation. Test the public proxy origin
and multiple replicas where deployed. Keep synthetic/mock, CI and live results
separate, including any operator action that remains unperformed.
