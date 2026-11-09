# Activity Analytics 1.3.5

Compatibility is intentionally pinned to DSH `0.2.2-rc.1`, the runtime whose
contracts were inspected. Source tests do not establish other-version or live
installed compatibility.

Profile-wide DSH Analytics sidebar page for user-active time and summed agent
working time. Local-only; no chat scan, input text, keystrokes, page names, or
external telemetry. Three concurrent agents running ten minutes count as thirty
agent-minutes. This is an estimate of presence, not a measurement of attention.

## Behavior

- User time estimates focused-window presence, not attention or manual work.
  A visible, focused window starts with a five-minute grace period even before
  trusted input. Trusted interaction renews it; five minutes without input pauses
  accounting. The grace period can include reading or inactivity.
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
  New v2 snapshots are immutable: each synchronous backup uses a fresh key,
  then removes only the exact snapshots durably replaced by that backup. Reload
  adopts and compacts captured v2 crash records; successful Host ACK retires them.
  A resumed live owner always publishes a new key, so cleanup cannot delete its
  newer tail. This works without Web Locks. Each construction requires a fresh
  random instance id; keys are never reused, including after failed writes.
  Rotation temporarily needs capacity for both old and new snapshots. Quota
  failures preserve source records and memory rather than deleting to make room;
  a full Host ACK can retire captured snapshots without allocating another one.
  Concurrent directory changes can defer recovery until another reload. If a
  failed write may have committed and a follow-up read also fails, its untouched
  key is left for fresh recovery rather than retaining an unbounded in-memory
  failed-attempt journal. Such ambiguous orphans may replay until that recovery.
  Legacy v1 records remain read-only and can replay: old writers do not honor the
  new protocol, and Browser Storage has no atomic compare/delete. Host union
  prevents double counting. No stale-record TTL or lossy eviction.
- Native unload closes admission, stops the timer and drains accepted work. Final
  SQLite flush gets one bounded retry; the connection is closed even on failure.
  A persistent storage failure is reported and may lose the final unsaved tail.

## Storage and deployment

Requires a DSH Host exposing usable `node:sqlite`; no npm runtime dependencies.
The bundle patch deliberately contains no machine paths. Storage root precedence
is explicit `profileDirectory`, then Host `DSH_PROFILE_DIR`, then the native
installed package's profile root. The native fallback requires an outer
`node_modules/@mainframe/activity-analytics` alias resolving to this exact package;
pnpm's inner self-reference is excluded. This relies on DSH's profile-local
package installation layout, not cwd or home guessing. Source-linked installs
without that anchor require explicit configuration; missing roots fail closed.

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

`locale/en.json` and `locale/ru.json` are the centralized translation owners:
`meta` supplies native plugin display metadata and the flat `ui` dictionary owns
all interface strings. Russian DSH uses Russian; every other DSH language uses
English, including dates, numbers and duration units. The Client registers the
embedded dictionaries through native `ctx.locale.register` and `bind`; native
locale slots and the page subscription update labels when DSH language changes.
No separate language setting is stored.

`time.js` and `outbox.js` are pure source modules. Edit `client.template.js` and
the locale JSON, then rebuild `client.js`; the generated runtime client embeds
both modules and the dictionaries using the shared development-only
`../build-locales.mjs`. Do not maintain translations inside the generated client. Tests use
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
