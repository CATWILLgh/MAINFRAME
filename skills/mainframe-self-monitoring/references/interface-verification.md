# Operator journey and acceptance

Build a native System/Diagnostics page: overall application state, dependency
cards, resource inventory and focused detail panels. Add Docker/Compose and data
preview tabs only for enabled capabilities. Show environment, collection time,
freshness and scope prominently. Use accessible labels, keyboard interaction,
responsive layout and the application's existing localization/design system.

Distinguish initial loading, valid zero, empty, unavailable, unsupported, forbidden,
stale and partial results. Preserve useful previous samples visibly marked stale;
charts show gaps rather than fabricated zeroes. Stop overlapping refreshes, discard
late responses from a previous target and isolate detail-panel failures. Logs need
bounded tails, optional follow, pause and safe copying without hidden secret data.

Actions name the environment and resource before confirmation; explain likely
interruption where relevant. Reflect server permissions and pending operations.
A lost response is unknown, not successful or automatically retryable. Reload
observed state and health separately from command acceptance. Never offer a
one-click destructive 'fix all' merely because a status card is red.

Use `mainframe-testing` and project-native tools. Test policy/formatting/collectors
in process, using bounded fake transports for denial, timeout, malformed response,
large payload and partial data. Use authorized isolated local PostgreSQL only
when its actual semantics are needed; other service integration and broad browser
matrices belong to the established CI route by default.

Required cases for selected capabilities:

- Unsupported runtime and failed metric fetch remain unknown, not healthy zero.
- Multiple viewers do not multiply unbounded collection; cancellation stops IO.
- Foreign tenant/project IDs are rejected on list, detail, logs and direct action.
- A proxied/local-looking Docker endpoint cannot be misclassified as disposable.
- Read-only socket mounts are never treated as Engine method authorization.
- Compose raw/default values, inspect fields and logs cannot bypass redaction.
- Action timeout, renamed/replaced container and stale UI selection do not restart
  a different resource or silently repeat the operation.
- Image removal excludes shared/rollback-required resources and reports actual
  outcomes without claiming sum-of-sizes equals freed storage.
- Data previews preserve tenant access, cost/byte limits and production consumer
  offsets; forbidden, empty and unavailable remain distinct.

Render and exercise the actual receiving app with synthetic values. Check safe
API payloads and persisted permissions as well as screenshots. Real Engine
reads, browser sessions and mutations establish different evidence. Perform live
operations only against explicitly authorized targets, with recovery and bounded
blast radius. Never stop a production dependency merely to demonstrate degradation.
A mocked dashboard or skill-plan evaluation is not live integration acceptance.

Selection probes should include building a services page without Docker, repairing
misleading resource charts and adding scoped container actions. A one-off restart,
Dockerfile optimization or standalone Grafana installation belongs to existing
infrastructure methods rather than this implementation skill alone.
