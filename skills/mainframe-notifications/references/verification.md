# Verify the notification slice

Use `mainframe-testing` for the project test boundaries and red/green workflow.
Keep pure formatting, policy, state transitions, fake transport and existing
local database checks lightweight. Real providers and supported-browser journeys
need separately authorized acceptance; mocks do not establish those outcomes.

Select cases for enabled channels and changed guarantees:

| Boundary | Required distinguishing evidence |
| --- | --- |
| Event durability | Rollback emits nothing; committed event survives worker restart; enqueue failure is visible; concurrent replicas cannot silently lose work. |
| Delivery identity | Duplicate event, expired lease and uncertain response follow explicit duplicate policy; completed destinations/parts are not blindly retried. |
| Routing | No-recipient/unknown channel fails explicitly; tenants cannot cross; settings changes do not redirect sensitive queued work. |
| Disable and expiry | Master/channel off and TTL are checked at attempts; pending pause/cancel and resume are defined; in-flight acceptance is reported honestly. |
| Isolation | Slow destination does not hold up all channels; queue, concurrency, retries and payload sizes remain bounded. |
| Secrets and settings | Reads expose presence, not values; keep/replace/clear work; stale concurrent saves are detected; provider errors do not leak credentials. |
| Bitrix24 | Existing registration does not update profile; update uses documented fields; missing ID is not success; pending rotation survives local-save failure; optional fetch cursor never acknowledges undurable events. |
| Telegram | Entity-aware limits, 429/retry_after, migrated chat ID and timeout-after-send ambiguity; no automatic paid broadcasts. |
| Webhook | Signature over exact bytes, tampering/replay/rotation, receiver dedup, expiry horizon, SSRF/redirect restrictions and truthful 202 semantics. |
| Email | Required TLS/AUTH failure; real socket cancellation; partial RCPT handling; lost DATA ack unknown; successful DATA then failed QUIT does not resend. |
| Web Push | Non-2xx with nil transport error, response closure, expired subscription, concurrent keys, backend registration failure, logout/account switch and approved click navigation. |
| UI | Master/channel/events controls persist; Save/Register/Test have distinct effects; secret unchanged; chosen draft/saved test target visible; disabled/failed/no-recipient states and keyboard access work. |

Include realistic selection probes without naming the skill: adding notification
settings, diagnosing duplicate email, implementing a signed outbound webhook, and
repairing browser subscription ownership should select this method. A one-off
message request, toast styling or deploying an SMTP server alone should not.

For UI acceptance render the actual receiving app with synthetic configuration,
exercise its controls and inspect persistence/network effects. Match the requested
information architecture and native design system rather than copying unrelated
branding or presenting a static screenshot as working behavior.

For each enabled channel, record the tested revision/configuration and distinguish
local tests, CI, provider acceptance, observed recipient receipt and unperformed
steps. A text-plan evaluation of this skill proves only the decisions expressed
in that response, not a working integration. Never send production test messages
or register/rotate external resources without authority for that action.
