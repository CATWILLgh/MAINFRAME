# Authentication and authorization

- Preserve the established auth system and trust boundaries. Auth.js sessions, Passport strategies, JWT/JWS via `jose`, OAuth/OIDC, API keys, and service tokens solve different problems.
- Verify credentials cryptographically and validate issuer, audience, expiry, algorithm, and key selection when the protocol requires them. Do not merely decode tokens.
- Derive identity from the verified server-side credential or session. Never accept a user or tenant identity from an untrusted body when it can be derived securely.
- Check authorization for the concrete resource and action close to the operation or data boundary. Authentication alone is not authorization.
- Treat Next.js middleware or proxy and hidden UI controls as convenience gates only; re-check privileged operations server-side.
- Keep browser sessions and refresh tokens in the project's established secure storage. Preserve CSRF, cookie, rotation, revocation, and logout semantics.
- Never log tokens, passwords, secrets, authorization headers, or session cookies.

Sources:
- OWASP Authentication Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Authorization Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- Auth.js — https://authjs.dev/
- Passport — https://www.passportjs.org/
