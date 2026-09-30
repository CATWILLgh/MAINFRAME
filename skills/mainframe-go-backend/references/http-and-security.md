# HTTP and security

Trace the served `http.Handler`, router mounting, middleware order, request
context, session/authentication middleware, error mapping, and response writer.
Preserve method, route, status, headers, media type, schema, pagination,
ordering, and error-envelope behavior unless changing that contract is assigned.

Bound request bodies and remote downloads. Validate path, query, header, and
decoded body values explicitly, including repeated parameters and the difference
between omitted, empty, zero, and invalid values. Decide unknown-field behavior
from the established API contract. Return after writing an error and avoid
partially written success responses.

Authenticate the presented credential and authorize the exact action on the
current resource using trusted server-side state. For cookies and sessions,
preserve Secure, HttpOnly, SameSite, expiry, rotation, revocation, origin and
CSRF behavior. Do not expose credential metadata, encrypted blobs, internal
audit details, raw provider payloads, or unnecessary personal data through a
convenient response projection.

Keep domain errors distinguishable with wrapping and `errors.Is`/`errors.As` so
the transport can map them without string matching. Preserve cancellation and
deadline causes. Log once at the owning boundary with stable request or
operation identifiers; never log secrets, session material, authorization
headers, signed URLs, or sensitive bodies.

Use `httptest` for the actual handler and middleware boundary. Direct handler or
store calls do not prove routing, authentication, origin checks, serialization,
headers, or status mapping.
