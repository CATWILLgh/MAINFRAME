# Browser safety

Treat network responses, URL and history state, browser storage, `postMessage`, pasted or uploaded content, rendered HTML, redirects, downloads, and third-party scripts as trust boundaries. Validate, sanitize, or constrain them according to their contract and consequence.

Never ship secrets in public environment variables, client bundles, static assets, source maps, fixtures, logs, analytics, or browser traces. Keep refresh tokens and long-lived credentials out of script-readable browser storage unless the project's established threat model explicitly accepts that design.

Types do not validate runtime data. Prefer owned generated types plus contract evidence, or runtime validation when the source is external, unstable, security-sensitive, or costly to mishandle.

Render untrusted HTML only through an appropriate sanitizer and reviewed policy. Preserve the correct parsing, transformation, sanitization, and rendering order; repeated incompatible sanitization is not automatically safer.

Keep the server authoritative for authorization, tenant isolation, protected mutations, and durable state. Browser visibility and disabled controls are not permission checks.

Verify installed framework, CSS tooling, and component-library versions before following migration advice. Do not upgrade them incidentally during a feature change.
