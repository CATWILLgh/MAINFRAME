# Files and external integrations

Treat object storage, external HTTP, push delivery, and generated documents as system boundaries. Preserve the project's adapter interfaces so local tests can replace infrastructure without pretending to reproduce its semantics.

## Object storage

- Store an opaque object key and metadata rather than trusting a user filename as a path. Normalize names for display separately.
- Validate authorization, size, media type from content where required, and lifecycle before upload or download. A client-provided MIME type is not proof.
- Stream large bodies and close SDK responses. Avoid loading an unbounded upload or download fully into process memory.
- Define database/object ordering and compensation for partial failure. Neither a database transaction nor an S3 operation atomically covers both systems.
- Treat bucket creation, retention, versioning, encryption, backup, and credentials as infrastructure decisions. Application code should not broaden policies during an ordinary file operation.
- Use a real S3-compatible service only when SDK, streaming, policy, presigned URL, or failure semantics are the risk; use an in-memory adapter for pure business rules.

## Outbound HTTP and push

- Set bounded connect and read timeouts. Retry only safe transient failures with limits and jitter; respect provider rate-limit guidance.
- Validate successful response shape before trusting it and distinguish timeout, transport failure, provider rejection, and malformed success.
- Prevent SSRF when destinations or redirects can be influenced externally. Keep credentials out of URLs, logs, exception text, and persisted payloads.
- Treat notification delivery as its own outcome. Remove or disable permanently rejected subscriptions where the provider contract supports it; do not hide systemic delivery failure as success.
- Keep personal or regulated data out of third-party notification payloads unless that transfer is an explicit product and compliance decision.

## Generated PDF, spreadsheet, QR, and exports

- Separate business data selection from rendering so the data contract can be tested without generating a binary artifact.
- Test the resulting artifact structurally: it opens, has expected sheets or pages, preserves required values and types, and handles Unicode, large content, formulas, and filenames safely.
- Escape spreadsheet formulas when user-controlled text must remain plain text. Bound row, image, archive, and memory growth.
- Use the installed library's current API and preserve templates, fonts, locale, and timezone contracts.

## Sources

- MinIO Python SDK — https://docs.min.io/aistor/developers/sdk/python/
- Requests advanced usage — https://requests.readthedocs.io/en/latest/user/advanced/
- OWASP SSRF prevention — https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- openpyxl — https://openpyxl.readthedocs.io/
- fpdf2 — https://py-pdf.github.io/fpdf2/
