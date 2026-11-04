# Activity Analytics 1.2.0

Profile-wide DSH Analytics sidebar page for user-active time and summed agent
working time. Local-only; no chat scan, input text, keystrokes, page names, or
external telemetry. Three concurrent agents running ten minutes count as thirty
agent-minutes. This is an estimate of presence, not a measurement of attention.

## Behavior

- User time requires a visible, focused DSH window and trusted input. Five minutes
  without input suspends accounting; the grace period can include reading.
- Agent time tracks all running agents in the active profile, including subagents,
  tool/model waits and parallel execution, starting when the plugin observes them.
- Today, yesterday, 7/14/28 calendar days, all-time and inclusive custom dates use
  the device's local calendar, including DST. Future time is excluded.
- Page totals and agent checkpoints update approximately every fifteen seconds.
  Overlapping browser activity is merged rather than double counted.
- Focus, IME, touch and trusted input handling is global to the DSH client. A
  scroll event alone is not proof of input. Hidden windows and other apps do not
  count. Isolated browser iframes/Desktop webviews may not report guest input;
  a native privacy-preserving bridge would be needed for full coverage.
- Sleep and timer gaps longer than thirty seconds are skipped. Browser batches
  contain at most 256 intervals of at most thirty seconds, retry idempotently,
  and remove queued time only after SQLite acknowledgement (`persistedThrough`).
- Numeric queues are backed up in profile/history-scoped browser localStorage.
  Failed backup/restore is visible, not silently discarded. Clear browser data,
  an unobserved crash tail or failure before first connection can still lose time.

## Storage and deployment

Requires a DSH Host exposing usable `node:sqlite`; no npm runtime dependencies.
The bundle patch deliberately contains no machine paths. Before activation,
configure `profileDirectory` for the **selected** profile through DSH's supported
plugin configuration; `DSH_PROFILE_DIR` is a fallback only and may be absent in
Desktop. Never guess the profile or point state into this source tree.

The profile's `activity-analytics/intervals.sqlite` stores only merged user
intervals, weighted agent intervals and history start. It is **not encrypted**;
activity timing is personal data. Directory mode 0700, files 0600, WAL and
`synchronous=FULL`; one DSH Host per profile. Corrupt history fails visibly rather
than resetting. Queries use indexed interval ranges; all-time scans matching
rows rather than loading and rewriting all history for every event.

On first open without SQLite, legacy `intervals.json` is validated and migrated
through a private temporary database, commit/fsync and atomic publication. The
original JSON remains unchanged as backup. Stop the old writer before migration.
Do not delete SQLite as a cache: it is authoritative history after migration.
For backup, stop DSH and copy the profile's analytics data directory. Linked local
bundle installations depend on their source directory: do not move/delete it.
The plugin never reads Secrets Vault data.

## Development and verification

From this package directory:

```sh
node build-client.mjs
node --check client.js
node --test *.test.mjs
```

`time.js` and `outbox.js` are pure source modules. Edit `client.template.js` and
rebuild `client.js`; the generated runtime client embeds both modules. Tests use
synthetic clocks and temporary data, including SQLite migration, failed writes,
concurrency/busy handling, corruption, randomized intervals, calendar boundaries,
privacy/focus/idle, queue ACK/retry/reload, quota failure and tooltip contracts.

`index.js` owns global agent lifecycle subscriptions and browser-only POST
`/api/activity-analytics/ui`, guarded by browser-peer admission and a dedicated
header. No agent tool can synthesize user activity. The Client uses supported
native slots, not foreign DOM or unstable internal Client packages. Inspect the
current Host/Client API contracts before changing integration code.

These are source tests, not proof of native activation or rendered UI. Verify
selected-profile registration, light/dark themes, real focus and browser reload
separately. Client HMR also requires the matching DSH web build watcher; source
changes alone do not promise an updated existing GUI.
