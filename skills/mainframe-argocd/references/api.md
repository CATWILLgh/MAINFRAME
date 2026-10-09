# REST API without guessed contracts

Read for REST integration or CLI-unavailable operations. Prefer the CLI when it
provides the same evidence safely. REST is not a bypass for RBAC or release authority.

## Resolve the contract and transport

- Use the target server's `/swagger-ui` and matching release OpenAPI schema.
  Confirm the route, HTTP method, parameters, request body and response shape.
  Do not send trial writes to learn the schema or paste flags into JSON.
- Keep the full HTTPS base URL, including any verified proxy prefix, separate
  from the CLI host/port. Validate scheme, host, port and prefix before attaching
  credentials. Do not follow authenticated redirects automatically.
- Deliver Bearer authentication from the existing approved credential mechanism
  inside the HTTP consumer. No expanded `Authorization` header in arguments,
  model context, debug logs, URLs or files. CLI config/SSO credentials are not
  material to scrape for an API token; use a correctly scoped existing token.
- Use a verified trust chain and bounded connection/request timeouts. Check
  transport result, HTTP status, JSON decoding and expected response fields.
  Filter sensitive response bodies before exposing output. Streaming logs or
  watch responses require their own bounded duration/size and decoder.

Source: [API documentation](https://argo-cd.readthedocs.io/en/stable/developer-guide/api-docs/).

## Application identity and endpoint families

Typical routes below are an orientation map; the target schema controls:

| Operation | REST route | Namespace/project placement |
| --- | --- | --- |
| Read one app | `GET /api/v1/applications/{name}` | Query `appNamespace`, `project` |
| Inspect resource tree | `GET /api/v1/applications/{applicationName}/resource-tree` | Query `appNamespace`, `project` |
| Submit sync | `POST /api/v1/applications/{name}/sync` | JSON body `appNamespace`, `project` |
| Remove app | `DELETE /api/v1/applications/{name}` | Query `appNamespace`, `project` |

Encode the app **name alone** as a path segment. Send its metadata namespace
separately as `appNamespace` in the location required by that endpoint, not the
destination workload namespace or a slash-joined name. Sync identity goes in
the body; a namespace in its query is not a substitute. If body `name` is included,
match the path name. Use URL/query and JSON builders, not string concatenation.
Include the established AppProject through the endpoint's `project` field.
Its use distinguishes missing apps from wrong-project access without leaking
other apps. A 403 is not proof that the app exists or that the token needs admin;
a 404 can also indicate the wrong namespace or proxy path. Resolve identity and
contract before recreating an app or widening access.

Source: [release schema](https://github.com/argoproj/argo-cd/blob/v3.2.0/assets/swagger.json),
checked as orientation only; use the installed release for requests.
The general API prose describes `project` as a query parameter for all app
endpoints; sync's operation-specific schema instead places it in the body.
Prefer that schema when the descriptions conflict.

## Writes and uncertain outcomes

Read [operations](operations.md) before a write. Construct the minimal body
using that operation's actual schema. For sync, explicitly establish revision(s),
resource selection, pruning, dry-run and sync strategy/options rather than relying
on remembered defaults. Re-read the app immediately before submission; avoid
racing an active operation or silently deploying a moved branch head.

Do not enable blanket HTTP retries for mutations. A connection loss, timeout or
gateway 5xx after submission may hide an accepted operation. Read that same app's
`operation`, `status.operationState`, resolved sync revision(s), timestamps and
resource outcomes. Determine whether the intended operation started, finished,
failed partially or is still unknown. Only resend when evidence establishes
that it was not accepted and authority still covers the same action. A new
submission is not an idempotency key; hooks may repeat external effects.

Treat 401 as authentication failure, 403 as an authorization/identity problem,
409 or an operation-in-progress error as a concurrency problem, and 429 as a
budget/backoff signal according to the actual response contract. Do not retry
bad schema/permission requests, replace an app on conflict, remove a finalizer
or switch to direct Kubernetes writes to make the response succeed.

Automation privileges should be scoped to the needed project/apps/actions;
token creation, expiration changes and RBAC edits require separate authority.
Validate exact permissions, including namespace-qualified application objects
when that feature is enabled. Do not assume `update` or `delete` grants every
resource sub-action on every version.

Sources: [security](https://argo-cd.readthedocs.io/en/stable/operator-manual/security/),
[RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/).
