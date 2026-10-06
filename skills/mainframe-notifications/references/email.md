# Email notification channel

Reuse a maintained MIME/submission library and the application's existing email
service. Separate envelope recipients from visible To/Cc/Bcc headers; prevent
cross-tenant recipient disclosure. Parse addresses, reject header injection,
encode subjects and bodies correctly, provide text alternatives to HTML and
escape template data. Keep stable Message-ID for traceability; it is not a
universal deduplication guarantee. Use explicit sender identities and authorized
recipients; never infer permission for bulk mail from notification development.

## Submission and cancellation

Configure implicit TLS (normally 465) or required STARTTLS (normally 587)
explicitly. If required STARTTLS or configured authentication is unavailable,
fail closed. Verify hostname/certificate, use supported TLS, and never silently
fall back to plaintext. Do not confuse local relay policy with arbitrary remote
submission. A local address alone does not prove a disposable test service.

Apply connection, handshake, command and whole-operation deadlines to the actual
socket. Returning from a context wrapper while a goroutine continues SMTP is not
cancellation and can produce late sends or duplicates. Close the transport on
cancellation and classify the last known protocol stage.

## Acceptance and retry

Track RCPT results per recipient and DATA completion. RCPT acceptance alone does
not mean the message was sent. If the transaction aborts before DATA, earlier
accepted RCPTs have not received that message. If policy allows proceeding with
some recipients, retain their individual outcomes and retry only appropriate
failed recipients; do not resend successful recipients indiscriminately.

A final positive response after DATA means the server accepted responsibility,
not inbox delivery. Failure of QUIT **after that response** must not turn the
message into a retryable send failure. Losing the DATA acknowledgement leaves
acceptance unknown; retries can duplicate. Classify temporary 4xx and permanent
5xx responses with their stage and recipient scope. Keep an explicit unknown
outcome policy rather than generic retry-on-error.

Bounces and delivery-status notifications are separate asynchronous evidence;
correlate and authenticate them if supported, without claiming universal delivery
or read receipts. Use existing domain/DNS operations for SPF, DKIM and DMARC;
do not make live DNS changes part of a routine settings save.

## Primary sources

Reviewed 2026-10-03:

- [RFC 5321: transactions, replies and timeout ambiguity](https://www.rfc-editor.org/rfc/rfc5321.html)
- [RFC 8314: secure submission](https://www.rfc-editor.org/rfc/rfc8314.html)
- [RFC 8997: modern TLS for email](https://www.rfc-editor.org/rfc/rfc8997.html)
- [RFC 5322: message format](https://www.rfc-editor.org/rfc/rfc5322.html)
- [Go SMTP semantics, including PlainAuth](https://pkg.go.dev/net/smtp)
