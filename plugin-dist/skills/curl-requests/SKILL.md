---
name: curl-requests
user-invocable: false
description: "HTTP(S) request templates and safe-defaults for `curl`: Bearer / Basic / `.netrc` auth, JSON GET/POST, multipart upload, healthcheck. Diagnostics — redirects, timeout (`--connect-timeout` + `--max-time`), retry whitelist (`--retry` covers HTTP 408 / 429 / 500-504 / 522 / 524 + connection timeouts, NOT arbitrary 4xx), header-only inspection (`-I` actually changes method to HEAD; `-i` keeps GET and just includes headers in output). Anti-patterns: hardcoded secrets, missing `--fail` / `--fail-with-body`, `-k` outside explicit debug, no `--max-time` on healthcheck, Basic over plain HTTP (cleartext), `--location` forwarding `Authorization` header to a cross-host redirect."
when_to_use: "An HTTP endpoint needs to be checked or driven from the terminal — explicit requests ('make a curl call / check an endpoint / send a request to an API'), API testing during recon or verification, downloading or uploading by URL, debugging a web service response, healthchecking a running container or service. Also applies when verifying a freshly-edited HTTP handler — curl against the endpoint surfaces status code and response shape without re-deploying."
---

# Working with curl

## Rules

1. Show the command before executing — unless it contains a secret in the URL or args.
2. Never inline secrets into the command or logs. Use environment variables, `-K` config file, or `.netrc`.
3. To gate on the response code, use `--fail` or `--fail-with-body` — both make non-2xx responses exit non-zero, with `--fail-with-body` keeping the body for diagnosis.

## Base templates

### GET (JSON) with response code

```bash
curl -sS --fail-with-body \
  -H "Accept: application/json" \
  -w "\nHTTP_CODE:%{http_code}\n" \
  "https://api.example.com/resource"
```

### POST JSON

```bash
curl -sS --fail-with-body -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"test"}' \
  -w "\nHTTP_CODE:%{http_code}\n" \
  "https://api.example.com/items"
```

### Bearer token (from env)

```bash
curl -sS --fail-with-body \
  -H "Authorization: Bearer ${API_TOKEN}" \
  "https://api.example.com/me"
```

The token comes from `$API_TOKEN` — never hard-coded in the command shown to the user or written to logs.

### Multipart upload

```bash
curl -sS --fail-with-body -X POST \
  -F "file=@./document.pdf" \
  -F "title=Report" \
  -w "\nHTTP_CODE:%{http_code}\n" \
  "https://api.example.com/upload"
```

### Quick healthcheck (no body)

```bash
curl -sS --fail -o /dev/null \
  --max-time 5 \
  -w "%{http_code}\n" \
  "https://example.com/health"
```

## Diagnostics

- **Redirects:** `-L` follows; `-vL` traces them. See the anti-pattern below about `Authorization` header on cross-domain redirects.
- **Timeouts:** `--connect-timeout N` caps the TCP/TLS connect phase only; `--max-time N` caps the whole operation (connect + redirects + body). Independent — set both.
- **Retries:** `--retry 3 --retry-delay 2 --retry-max-time 30`. By default curl retries on a fixed whitelist: connection timeouts, FTP 4xx, and HTTP `408`, `429`, `500`, `502`, `503`, `504`, `522`, `524` (per `curl.se/cvssource/docs/cmdline-opts/retry.md`). Other 4xx are not retried. `--retry-all-errors` widens this to any curl-level error including arbitrary HTTP failures (use deliberately — it can mask real client bugs).
- **Headers vs HEAD:** `-I` (`--head`) issues an HTTP **HEAD** request — the server returns headers only, no body sent. `-i` (`--include`) issues whatever method you chose (default GET) and prints response headers along with the body to stdout. These are not interchangeable: `-I` changes the request method; `-i` only changes the output. Use `-D headers.txt -o body.json` to split headers and body to separate files.

## Safe authentication

**Where tokens come from.** If [`secrets-handling`](../secrets-handling/SKILL.md) is active on this machine, generic API tokens live in `~/.config/credentials/secrets.env` and are loaded into the shell environment by `~/.zshenv`. The patterns below assume this — `$API_TOKEN` resolves because the store was sourced at shell start. If the token is in the store but not in the current shell env (e.g. just added via `secret set`), substitute inline: `$(secret get API_TOKEN)`. If `secrets-handling` is not active, treat the env-var examples as "replace with whatever your project's credential source is" (vault CLI, project `.env`, etc.) — the curl patterns themselves are agnostic.

- **Bearer:** token only from env (`API_TOKEN` or similar). Never echo the variable; never include in the displayed command if the user could see logs.
- **Basic:** prefer `.netrc` + `-n` so the password is not in the command line:
  - `~/.netrc` with mode `600`:
    ```
    machine api.example.com
    login myuser
    password mypassword
    ```
  - Command: `curl -sS -n "https://api.example.com/protected"`
  - In scripts: `--netrc-optional` (use `.netrc` if present, no hard requirement) or `--netrc-file <path>` (explicit file) are more robust than bare `-n`.
- **`-u user:pass`:** avoid when the command line is visible. Per the curl FAQ, curl tries to blank the password from the process listing, but this is **not guaranteed on all platforms** — there is a race between fork and the blanking. `.netrc` removes the race entirely.

## Anti-patterns

- **Hardcoded secrets in the visible command** — token or password in plain args; goes to history, screen sharing, log capture.
- **Missing `--fail` / `--fail-with-body`** — curl exits 0 on 4xx/5xx by default; the script silently treats failures as success.
- **`-k` / `--insecure` outside explicit user-approved debugging** — disables TLS certificate verification; per the curl FAQ, this enables MITM and is "strongly advised against … for more than experiments". Acceptable only for local-only self-signed dev certs the user named.
- **No `--max-time` on a healthcheck** — a hung endpoint hangs the loop forever; pair with `--connect-timeout`.
- **Basic auth over plain HTTP** (not HTTPS) — credentials are sent cleartext. Per the curl FAQ, regular HTTP Basic and FTP passwords go in the clear.
- **`--location` (`-L`) with an `Authorization` header to an untrusted destination** — by default curl forwards request headers including `Authorization` across same-host redirects, and `--location-trusted` extends this to cross-host redirects. A chain redirecting to a third-party domain can leak the token. When following redirects with auth, verify the redirect target host first, or fetch the redirect URL via `-I` and re-send auth only to the expected host.

## Cross-refs

- [`secrets-handling`](../secrets-handling/SKILL.md) — where tokens / passwords come from on this machine, how to substitute them without leaking the value into the response.
- [`ops-app-server-safety`](../ops-app-server-safety/SKILL.md) — before curling a freshly-started local dev server, confirm only one instance is running on the port.
