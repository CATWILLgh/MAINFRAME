# Browser safety and version boundaries

- Treat network responses, storage, URL state, `postMessage`, pasted content, uploaded files, and third-party scripts as trust boundaries. Validate or sanitize according to the contract and consequence of malformed data.
- Type assertions do not validate runtime data. Prefer owned generated types plus contract tests, or runtime schemas where the source is external, unstable, security-sensitive, or costly to mishandle.
- Never ship secrets in `VITE_*`, `NEXT_PUBLIC_*`, source maps, static assets, fixtures, or client logs. Public identifiers are not secrets; credentials and signing material are.
- Preserve the project's established session design. Refresh tokens and long-lived credentials should not be placed in browser storage where injected script can read them.
- Render untrusted HTML only through an appropriate sanitizer and a reviewed policy. A trusted server pipeline must remain documented and tested; avoid sanitizing twice in incompatible ways.
- Confirm Tailwind, CSS tooling, component-library, and framework majors before using configuration or migration advice. Do not silently upgrade styling infrastructure during a feature change.
- Restrict browser permissions and external content to the minimum capability required, and provide failure behavior when a browser denies or lacks the feature.

Sources:
- OWASP Cross Site Scripting Prevention — https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html
- OWASP HTML5 Security — https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
- Vite environment variables — https://vite.dev/guide/env-and-mode
- Next.js environment variables — https://nextjs.org/docs/app/guides/environment-variables
