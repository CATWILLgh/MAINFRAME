# Authentication and authorization

- Preserve the established trust boundary. Sessions, Passport strategies,
  JWT/JWS, OAuth/OIDC, API keys, and service tokens solve different problems.
- Verify credentials cryptographically and validate issuer, audience, expiry,
  algorithm, and key selection when the protocol requires them. Decoding is not
  verification.
- Derive identity from the verified server credential or session. Do not accept
  user or tenant identity from an untrusted payload when it can be derived.
- Authorize the concrete resource and action close to the operation or data
  boundary. Authentication alone is insufficient.
- Treat Next.js middleware, proxy checks, and hidden UI controls as convenience
  gates; re-check privileged operations server-side.
- Preserve CSRF, cookie, token rotation, revocation, and logout semantics.
- Never log passwords, tokens, secrets, authorization headers, or session
  cookies.

Sources: [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[OWASP authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html),
[Auth.js](https://authjs.dev/), [Passport](https://www.passportjs.org/).
