---
name: mainframe-curl-requests
description: Build and run bounded HTTP(S) requests with curl while preserving request authority, credential safety, explicit timeouts, correct status handling, and safe retry and redirect behavior. Use when checking or driving an endpoint from the terminal, verifying an API handler, uploading or downloading by URL, diagnosing a service response, or running a health check. Do not use when a purpose-built client provides the same evidence more safely.
---

# Curl requests

Use curl as a narrow transport tool, not as authority to mutate an external
system. Establish the intended method, target environment, endpoint contract,
and observable result before sending the request. A diagnostic task does not
authorize POST, PUT, PATCH, DELETE, deployment, or another side effect.

## Safe defaults

- Put `--disable` first so an uninspected user-level `.curlrc` cannot silently
  add redirects, credentials, proxies, output paths, or weaker transport
  settings. Omit it only when the assigned operation explicitly depends on a
  known curl config.
- Use HTTPS unless the target is a verified local plaintext service.
- Set `--connect-timeout` and `--max-time` from the operation's expected
  latency. A health check should be short; a known upload may need longer.
- Use `--fail-with-body` when an HTTP status of 400 or greater must produce a
  failing exit code while retaining the error body for local diagnosis. Use
  `--fail` when the body is unnecessary or may contain sensitive data. These
  options do not treat 3xx as failure.
- Add `-sS` when machine-readable output is useful. Preserve the status code
  separately with `--write-out` when the result must prove both transport and
  application behavior.
- Let `--data`, `--form`, and other data options select their normal request
  method. Do not add `-X POST` unless the server contract specifically requires
  overriding curl's method selection.
- `-I` sends a HEAD request. `-i` preserves the selected method and includes
  response headers in output. They are not interchangeable.

```bash
curl --disable -sS --fail-with-body \
  --connect-timeout 3 --max-time 15 \
  -H "Accept: application/json" \
  --write-out "\nHTTP_CODE:%{http_code}\n" \
  "https://example.invalid/resource"
```

For JSON, preserve the endpoint's documented schema:

```bash
curl --disable -sS --fail-with-body \
  --connect-timeout 3 --max-time 15 \
  -H "Content-Type: application/json" \
  --data '{"name":"example"}' \
  "https://example.invalid/items"
```

## Credentials and output

Read [`mainframe-secrets`](../mainframe-secrets/SKILL.md) before an authenticated
request. Use the credential name and header scheme recorded in the
[credentials index](../../../../shared/credentials/credentials-index.md);
do not assume Bearer authentication.

Pass a registered value directly to curl, for example:

```bash
curl --disable -sS --fail \
  -H "x-api-key: $(secret get REGISTERED_NAME)" \
  "https://example.invalid/health"
```

Do not use verbose or trace output with credentials unless the output is kept
out of model context and safely redacted. Do not return request headers, raw
authenticated URLs, cookie jars, environment dumps, or an unreviewed response
body. Prefer `.netrc` or another native credential mechanism when the index
specifies it; never read that backing file.

## Retries and redirects

- Retry only when the operation is safe to repeat or the API supplies a proven
  idempotency mechanism. Do not add retries to a state-changing request merely
  because curl supports them.
- `--retry N` covers curl's documented transient set, including timeouts and
  HTTP 408, 429, 500, 502, 503, 504, 522, and 524. Bound the total with
  `--retry-max-time`. `--retry-all-errors` is not a default: it can duplicate
  sent or received data.
- Do not follow a redirect carrying a custom secret header unless every target
  origin is trusted. `--location` withholds command-line authentication and the
  `Authorization` and `Cookie` headers from another origin, but it repeats other
  custom headers there, including an `x-api-key` header. Prefer inspecting the
  redirect first and issuing a separate bounded request.
- `--location-trusted` additionally permits credentials and other secrets to
  cross a hostname, scheme, or port boundary; use it only when that forwarding
  is explicitly required and every destination is verified.
- When redirects are required, bound their count with `--max-redirs` and allow
  only the required protocols with `--proto-redir`.

## TLS and files

Do not use `--insecure` to make a remote request succeed. For an explicitly
assigned local self-signed environment, prefer its CA certificate; if temporary
insecure diagnostics are the only remaining option, report the evidence limit
instead of treating that result as production-valid.

For downloads and uploads, resolve the exact local path first, avoid overwriting
unrelated files, and keep credentials out of filenames and URLs. Use a temporary
file when the response must be inspected before it receives its final name.

## Sources

- [curl command-line manual](https://curl.se/docs/manpage.html)
- [`--disable`](https://curl.se/docs/manpage.html#--disable)
- [`--fail-with-body`](https://curl.se/docs/manpage.html#--fail-with-body)
- [`--retry`](https://curl.se/docs/manpage.html#--retry)
- [`--header`](https://curl.se/docs/manpage.html#--header)
- [`--location`](https://curl.se/docs/manpage.html#--location)
- [`--location-trusted`](https://curl.se/docs/manpage.html#--location-trusted)

Before relying on a version-sensitive option, check the installed
`curl --version` and the current manual.
