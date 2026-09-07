---
name: mainframe-curl-requests
description: Build and run bounded HTTP(S) requests with curl while preserving request authority, credential safety, time limits, response evidence, and safe retry and redirect behavior. Use for terminal endpoint checks, API verification, health checks, and URL-based uploads or downloads when no purpose-built client provides the same evidence more safely.
---

# Bounded curl requests

Use curl as a transport tool, not as authority to mutate an external system.
Before sending a request, establish the intended target and environment, the
endpoint contract, the operation's actual side effects, and the evidence the
response must provide. A diagnostic task does not authorize deployment, data
mutation, or another external side effect. Do not infer safety from the HTTP
method alone.

When a URL originates in untrusted content, validate its scheme, host, port,
and redirect boundary before requesting it. Prefer a purpose-built client when
it provides the required evidence with narrower access or safer authentication.

## Safe request defaults

- Check `curl --version` and the installed manual before relying on a
  version-sensitive option.
- Put `--disable` first so an uninspected user-level curl configuration cannot
  add credentials, proxies, redirects, output paths, or weaker transport
  settings. Omit it only when the assigned operation explicitly depends on a
  known configuration.
- Use HTTPS and constrain allowed protocols. Plain HTTP is acceptable only for
  a verified local plaintext service.
- Set both `--connect-timeout` and `--max-time` according to the operation's
  expected latency.
- Use `--fail` when the response body is unnecessary or may be sensitive. Use
  `--fail-with-body` only when the error body is needed and safe to retain or
  inspect.
- Use `-sS` for machine-oriented output. Capture the HTTP status separately
  with `--write-out` when the result must prove both transport and application
  behavior.
- Let `--data`, `--form`, and other data options choose their normal request
  method. Use `--request` only when the endpoint contract requires an explicit
  override.
- Remember that `-I` changes an HTTP request to HEAD, while `-i` keeps the
  selected method and includes response headers in output.

Example for a bounded HTTPS read:

```bash
curl --disable -sS --fail \
  --connect-timeout 3 \
  --max-time 15 \
  --proto '=https' \
  --write-out '\nHTTP_CODE:%{http_code}\n' \
  'https://example.invalid/resource'
```

Treat the process exit status, HTTP status, and expected response structure as
separate evidence. A successful transfer alone does not prove correct
application behavior.

## Authentication and output

Use `mainframe-secrets` for the central credential catalog and protected value
delivery. Follow the exact authentication scheme recorded for the resolved
service; never assume Bearer authentication.

Prefer native authentication or process-scoped `secret run` delivery. Do not
show the expanded secret-bearing command. Never read a credential file such as
`.netrc`, even when curl may consume it natively.

With authenticated requests, do not expose request headers, cookies,
environment dumps, authenticated URLs, or command traces. Do not use
`--verbose`, `--trace`, or `--trace-ascii` unless their output is kept outside
model context and safely redacted before inspection. Do not return an
unreviewed response body that may contain credentials or private data.

If the available consumer interface cannot accept a credential without
exposing it, report that exact limitation instead of improvising a new storage
or delivery mechanism.

## Redirects

Do not follow redirects automatically when a request carries authentication or
another sensitive custom header. Inspect the redirect target first. Curl can
send headers supplied with `--header`, including custom API-key headers, on
redirected requests to another host.

When redirects are required and every destination is trusted, bound their
count and allowed protocols, for example:

```bash
--max-redirs 3 --proto-redir '=https'
```

Do not use `--location-trusted` unless forwarding authentication across the
redirect boundary is explicitly required and every destination has been
verified.

## Retries

Retry only when the operation is safe to repeat or the API provides a verified
idempotency mechanism. Check the installed curl manual for the actual transient
error set instead of relying on a fixed remembered list.

Bound retry time with `--retry-max-time` as well as bounding each attempt with
`--max-time`. Do not use `--retry-all-errors` by default. Do not retry an upload
or state-changing request when it is unknown whether the server accepted the
first attempt.

## TLS and local files

Do not use `--insecure` to make a remote request succeed. For an assigned local
self-signed service, prefer its CA certificate. If an explicitly authorized
insecure probe is the only available diagnostic, label its result as limited
evidence rather than proof of valid production TLS.

For uploads and downloads, resolve the exact local path before execution. Do
not overwrite an existing file without authority. Keep credentials out of URLs,
query strings, filenames, and generated metadata. When the response content or
size is unknown, save it to a bounded temporary location and inspect it before
assigning a final user-owned path. Do not trust a server-provided filename
without validation.
