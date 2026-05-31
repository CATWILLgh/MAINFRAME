# Safety — boundaries, secrets, XSS, Tailwind version

Frontend-side floor. Reproduce-on-server is mandatory but lives in the backend agents — these rules are about NOT leaking through the client.

## Validate at every data boundary

Per OWASP Input Validation Cheat Sheet, untrusted data crosses the trust boundary the moment it enters the app — typed annotations on `fetch().then(r => r.json() as ApiResponse)` are NOT validation.

```ts
const ApiResponse = z.object({ id: z.string(), email: z.string().email() })
const raw = await fetch(url).then(r => r.json())
const data = ApiResponse.parse(raw)   // throws on shape mismatch — caught at the HTTP-client layer
```

Place the parse inside the HTTP-client / mapper. UI never sees unvalidated shapes. Same rule for `localStorage.getItem(...)` and `postMessage` payloads — boundaries, validate.

## Secrets, tokens, env vars

- **Refresh tokens never in `localStorage` / `sessionStorage`.** Per OWASP DOM-based XSS Prevention: any XSS reads the entire storage. Use `httpOnly` cookies set by the server.
- **Access tokens — memory only**, or `httpOnly` cookie. Refresh-on-401 against a server endpoint that owns the rotation.
- **`VITE_*` env vars are bundled into the client JS.** Anyone with DevTools sees them. Never put API secret keys, OAuth client secrets, signing keys there. Public identifiers (analytics IDs, public Stripe keys) are fine; anything else is a leak.
- **Errors logged to Sentry / console — redact PII.** Whitelist fields; do not dump entire request bodies.

## `dangerouslySetInnerHTML` — only with DOMPurify

User-controlled HTML → DOMPurify (or equivalent) first. Server-trusted HTML (e.g. rendered Markdown the backend already sanitised) — OK to render directly, but annotate the source so future readers see the trust assumption. Per OWASP XSS Prevention Cheat Sheet: «context-aware output encoding» is the floor; bypass only with a sanitiser.

## Tailwind v3 → v4 — different setup, different defaults

If recon reported `tailwind: v4`:

- Config lives in the CSS file via `@theme` directive; `tailwind.config.js` is removed.
- Import via `@import "tailwindcss"`, NOT `@tailwind base; @tailwind components; @tailwind utilities`.
- Colors via OKLCH preferred — `hsl(...)` wrappers in `chartConfig` removed.
- `tailwindcss-animate` is deprecated; use `tw-animate-css`.
- shadcn primitives no longer use `React.forwardRef` — they use `React.ComponentProps<T>` + a `data-slot` attribute.

If recon reported `tailwind: v3` and the work is **not** a Tailwind migration — leave v3 in place, do not silently upgrade. Migration is its own scoped change.

## Anti-patterns

- `as ApiResponse` on a `fetch().json()` result — boundary not validated.
- `localStorage.setItem('refreshToken', ...)` — XSS-exposed secret.
- `VITE_STRIPE_SECRET_KEY` — shipped in the bundle, found in 30 seconds by anyone with DevTools.
- `dangerouslySetInnerHTML={{ __html: comment.body }}` without DOMPurify — XSS injection vector.
- Catching every `fetch` error with a single «something went wrong» — the user cannot diagnose, the dev cannot reproduce.

## Sources

- OWASP Input Validation — https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
- OWASP DOM-based XSS Prevention — https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html
- OWASP XSS Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- Vite — env vars surface — https://vite.dev/guide/env-and-mode
- Tailwind v4 release notes — https://tailwindcss.com/blog/tailwindcss-v4
- shadcn/ui Tailwind v4 migration — https://ui.shadcn.com/docs/tailwind-v4
