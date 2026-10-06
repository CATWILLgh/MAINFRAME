# Browser Web Push

Web Push is a browser subscription channel, not a generic webhook or an in-page
toast. Separate administrators' channel settings from each user's consent and
device subscription. Reuse the app's service worker; do not replace its caching,
update or offline behavior unconditionally.

## Identity and lifecycle

Require a secure context and appropriate service-worker scope. Request permission
from an explicit user gesture; prefetch required configuration so an awaited
network request does not lose that gesture. Handle denied, unsupported and revoked
permission without repeated prompts. Browser support can depend on platform and
installation mode; verify the project's actual target browsers.

Bind create/read/delete and delivery to authenticated user, tenant and device
ownership on the server. Permission in a browser is not backend account
ownership. A subscription existing locally does not prove successful server
registration. Reconcile both sides, avoid needless re-subscription, and clean up
obsolete server records. On logout/account switch prevent notifications for the
previous identity, including pending deliveries; do not let a failed backend
cleanup leave the UI falsely claiming unsubscribe succeeded. Provide an explicit
recovery state for a partially completed unsubscribe.

Treat endpoint URLs and subscription authentication material as credentials.
Never log complete endpoints. Guard server-side endpoint requests against SSRF
using the supported push-service contract; do not treat arbitrary client URLs as
trusted. Retain only necessary device metadata and minimize lock-screen content.

## Keys and payload

Persist VAPID keys durably across replicas; avoid concurrent initialization that
creates incompatible key pairs. Rotation requires an explicit subscription
migration plan. VAPID identifies the application server, not the logged-in user;
payload encryption uses separate keys and the subscription's p256dh/auth values.
Use a maintained implementation of ES256/P-256 VAPID and aes128gcm encryption.
Verify the selected library version's contact format, public/private key options,
audience and expiry handling; an example for another version is not proof.
VAPID expiry must be no more than 24 hours ahead, with the push-service origin as
audience. Never reuse the signing key for encryption.

Set TTL from event usefulness, including explicit zero-TTL semantics. Bound the
encrypted payload to service limits; the standard 4096-byte minimum capacity is
not 4096 bytes of arbitrary plaintext. Avoid sensitive bodies when a minimal
notification and an authenticated app fetch suffice.

## Response and browser handling

Inspect HTTP responses even if the client reports no transport error. Close
response bodies. Service acceptance (normally 201) is not device delivery.
Remove the affected subscription on verified 404/410 expiry responses; coordinate
cleanup so an old job cannot delete a newly replaced record. Honor 429/Retry-After;
fix malformed/oversized requests rather than repeatedly retrying 400/413.
Unknown transport outcomes retain duplicate risk. Provider receipts, device
receipt and user interaction are separate evidence, if actually available.

Validate service-worker payload shape and constrain click navigation to approved
origins/routes. Resolve then compare URL origins exactly; string prefixes and
openWindow do not enforce same-origin safety. Recheck authorization when the app
opens. Test permission, subscription, account switching, push display and click
behavior in supported browsers; server-only mocks cannot prove them.

## Primary sources

Reviewed 2026-10-03:

- [Push API: subscriptions and privacy](https://www.w3.org/TR/push-api/)
- [RFC 8030: TTL, acceptance, expiration and security](https://www.rfc-editor.org/rfc/rfc8030)
- [RFC 8291: encryption and payload sizes](https://www.rfc-editor.org/rfc/rfc8291)
- [RFC 8292: VAPID](https://www.rfc-editor.org/rfc/rfc8292)
- [WebKit: permission gesture and browser integration](https://webkit.org/blog/12945/meet-web-push/)
- [Browser-provider error guidance](https://web.dev/articles/push-notifications-common-issues-and-reporting-bugs)
- [Service worker openWindow](https://www.w3.org/TR/service-workers/#clients-openwindow)
