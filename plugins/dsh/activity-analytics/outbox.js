/* Pure browser-compatible, synchronous interval outbox. No ambient storage/DOM access.
 *
 * The caller MUST supply a fresh, globally unique opaque instance id for EVERY
 * construction, including reloads (e.g. crypto.randomUUID()), and an authenticated
 * profile scope. Keys contain only these identifiers and a monotonic sequence;
 * values contain a version and numeric half-open epoch-ms intervals.
 *
 * v2 snapshots are immutable: each persist writes the complete current union to
 * a fresh key BEFORE removing the exact captured old snapshots. A key is never
 * reused, even after deletion or a failed/ambiguous write. Another live owner can
 * append safely by publishing a fresh key, which our captured cleanup cannot touch.
 * Absence checks defend persisted id collisions, NOT simultaneous id reuse (there
 * is no Storage CAS). Fresh ids also prevent reuse of already-deleted identities.
 *
 * Recovery reads v1 and v2. Mutable v1 records remain strictly read-only, forever
 * replayable: an old tab can change them even between a comparison and deletion.
 * Host interval union makes duplicate delivery harmless. Removal failures retry
 * on later add/ACK calls; malformed/unreadable records are preserved. Rotation
 * temporarily needs room for old AND new snapshots: quota failure never deletes
 * sources first and retains the current memory union, reported as volatile. A
 * failed write whose commit cannot be read is left untouched for the next fresh
 * recovery, not retained as an unbounded in-memory journal of failed attempts.
 * No queue cap, per-event journal, timers, leases, locks, or storage events.
 */

const OUTBOX_LEGACY_PREFIX = 'activity-analytics:outbox:v1:';
const OUTBOX_PREFIX = 'activity-analytics:outbox:v2:';
const OUTBOX_MAX_EPOCH = 8_640_000_000_000_000;
const OUTBOX_MAX_BATCH = 256;
const OUTBOX_MAX_INTERVAL = 30_000;

function outboxRange(start, end) {
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) ||
      start < 0 || end > OUTBOX_MAX_EPOCH || end <= start) {
    throw new TypeError('Expected a valid positive UNIX epoch millisecond interval.');
  }
  return [start, end];
}

function outboxUnion(intervals) {
  const result = [];
  for (const [start, end] of intervals.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const last = result[result.length - 1];
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else result.push([start, end]);
  }
  return result;
}

function outboxInput(intervals, end) {
  if (end !== undefined) return [outboxRange(intervals, end)];
  if (!Array.isArray(intervals)) throw new TypeError('Expected an array of intervals.');
  return intervals.map(value => {
    if (Array.isArray(value) && value.length === 2) return outboxRange(value[0], value[1]);
    if (value && typeof value === 'object' && !Array.isArray(value)) return outboxRange(value.start, value.end);
    throw new TypeError('Expected numeric interval endpoints.');
  });
}

function outboxSubtract(pending, acknowledged) {
  const result = [];
  let index = 0;
  for (const [start, end] of pending) {
    let cursor = start;
    while (index < acknowledged.length && acknowledged[index][1] <= cursor) index++;
    let current = index;
    while (current < acknowledged.length && acknowledged[current][0] < end) {
      const [from, until] = acknowledged[current];
      if (from > cursor) result.push([cursor, from]);
      cursor = Math.max(cursor, until);
      if (cursor >= end) break;
      current++;
    }
    if (cursor < end) result.push([cursor, end]);
    index = current;
  }
  return result;
}

function outboxRecord(raw, version) {
  const value = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value) || value.version !== version ||
      Object.keys(value).some(key => key !== 'version' && key !== 'pending') || !Array.isArray(value.pending)) {
    throw new TypeError('Invalid outbox record.');
  }
  const intervals = value.pending.map(row => {
    if (!Array.isArray(row) || row.length !== 2) throw new TypeError('Invalid outbox record.');
    return outboxRange(row[0], row[1]);
  });
  return outboxUnion(intervals);
}

/**
 * add([{start,end}]) (or add(start,end)); getBatch() returns detached host-shaped
 * intervals, at most 256 of <=30000ms. ack(batch) subtracts only those exact
 * intervals from the CURRENT union, retaining any concurrently appended tail.
 * Call ack only after Host success. getPending()/pendingIntervals() return copies;
 * pendingMs() reports the union duration. onState is synchronous, including restore.
 * getState(): {pendingMs,pendingCount,durable,error,recoveryError}. Error strings
 * are generic: storage exceptions/keys/raw values never leak into UI diagnostics.
 * scope:null is intentional pre-authentication memory-only mode, touching no keys.
 */
export function createOutbox({ storage = null, scope = null, id, onState } = {}) {
  if (typeof id !== 'string' || id.length === 0) throw new TypeError('A unique opaque outbox id is required.');
  if (scope !== null && (typeof scope !== 'string' || scope.length === 0)) throw new TypeError('Expected an opaque nonempty scope.');
  if (onState !== undefined && typeof onState !== 'function') throw new TypeError('onState must be a function.');
  const prefix = scope === null ? null : `${OUTBOX_PREFIX}${encodeURIComponent(scope)}:`;
  const legacyPrefix = scope === null ? null : `${OUTBOX_LEGACY_PREFIX}${encodeURIComponent(scope)}:`;
  const ownPrefix = prefix === null ? null : `${prefix}${encodeURIComponent(id)}:`;
  let sequence = 0;
  // Captured immutable identities only, never a fresh directory scan for cleanup.
  // Their intervals are covered by pending or a Host ACK, so retirement can retry.
  const snapshots = new Map();
  let pending = [];
  let durable = false;
  let error = null;
  let recoveryError = null;

  const pendingMs = () => pending.reduce((total, [start, end]) => total + (end - start), 0);
  const getPending = () => pending.map(([start, end]) => ({ start, end }));
  const getState = () => ({ pendingMs: pendingMs(), pendingCount: pending.length, durable, error, recoveryError });
  function notify() {
    // UI observer failure must not turn a successfully retained sample into loss.
    try { onState?.(getState()); } catch { /* State remains available via getState(). */ }
  }
  function persist() {
    durable = false;
    if (scope === null) return;
    let key;
    let raw;
    let attempted = false;
    try {
      if (!storage || typeof storage.getItem !== 'function' || typeof storage.setItem !== 'function' ||
          typeof storage.removeItem !== 'function') throw new TypeError('Unavailable storage.');
      if (pending.length) {
        do {
          if (sequence === Number.MAX_SAFE_INTEGER) throw new TypeError('Snapshot sequence exhausted.');
          // Consume BEFORE checking/writing: failures may have committed, and a
          // reader can already hold this identity for a later retirement.
          key = `${ownPrefix}${++sequence}`;
        } while (storage.getItem(key) !== null);
        raw = JSON.stringify({ version: 2, pending });
        attempted = true;
        storage.setItem(key, raw);
      }
    } catch {
      if (attempted) {
        try {
          const current = storage.getItem(key);
          // setItem can commit and then throw. Only confirmed, exact committed
          // snapshots need tracking. Absent keys never return (fresh ids/sequence).
          if (current === raw) snapshots.set(key, raw);
          else if (current !== null) {
            recoveryError = 'A changed saved activity record was preserved and could not be retired.';
          }
        } catch {
          // Do not accumulate full snapshots for every ambiguous failure during
          // storage outage. Leave any possible commit intact for fresh recovery.
          recoveryError = 'A failed activity write could not be checked; any saved snapshot was preserved for the next recovery.';
        }
      }
      error = 'Activity storage is unavailable; unsynced activity may only be in memory.';
      return; // No source deletion on failed/ambiguous replacement.
    }
    // Capture known old identities only after successful publication, before
    // recording its fresh key. Failed writes need not copy the retirement set.
    const captured = [...snapshots];
    if (attempted) snapshots.set(key, raw);
    let cleaned = true;
    for (const [key, raw] of captured) {
      try {
        const current = storage.getItem(key);
        if (current !== null && current !== raw) {
          // Defensive isolation for corrupted or nonconforming writers. This
          // check is NOT CAS: safety still requires immutable v2 identities.
          recoveryError = 'A changed saved activity record was preserved and could not be retired.';
        } else if (current !== null) {
          storage.removeItem(key);
        }
        snapshots.delete(key);
      } catch {
        cleaned = false; // Keep this exact identity for a later safe retry.
      }
    }
    // Pending is now fully persisted (or empty after ACK/empty recovery). A
    // cleanup failure leaves duplicate replay, not volatile unacknowledged data.
    durable = true;
    error = cleaned ? null : 'Activity is retained, but saved snapshots could not be retired; cleanup will retry.';
  }

  if (scope !== null) {
    const recovered = [];
    try {
      if (!storage || typeof storage.getItem !== 'function' || typeof storage.key !== 'function') {
        throw new TypeError('Unavailable storage.');
      }
      // Snapshot the directory BEFORE any cleanup. Racing insertions/removals can
      // skip a key; an unseen record stays untouched for a later recovery.
      const keys = new Set();
      const count = storage.length;
      if (!Number.isSafeInteger(count) || count < 0) throw new TypeError('Unavailable storage directory.');
      for (let index = 0; index < count; index++) {
        const key = storage.key(index);
        if (typeof key === 'string' && (key.startsWith(prefix) || key.startsWith(legacyPrefix))) keys.add(key);
      }
      for (const key of keys) {
        // Defensive id-collision handling also consumes observed old sequences;
        // compacting one must never make its identity available to this instance.
        if (key.startsWith(ownPrefix)) {
          const suffix = key.slice(ownPrefix.length);
          const seen = Number(suffix);
          if (/^[1-9][0-9]*$/.test(suffix) && Number.isSafeInteger(seen)) sequence = Math.max(sequence, seen);
        }
        let raw;
        try { raw = storage.getItem(key); } catch {
          recoveryError = 'Some saved activity could not be recovered; existing records were preserved.';
          continue;
        }
        if (raw === null) continue;
        try {
          const version = key.startsWith(prefix) ? 2 : 1;
          if (version === 2) {
            const suffix = key.slice(prefix.length);
            const match = /^[^:]+:([1-9][0-9]*)$/.exec(suffix);
            if (!match || !Number.isSafeInteger(Number(match[1]))) throw new TypeError('Invalid snapshot key.');
          }
          for (const interval of outboxRecord(raw, version)) recovered.push(interval);
          if (version === 2) snapshots.set(key, raw);
        } catch {
          recoveryError = 'A malformed saved activity record was preserved and could not be recovered.';
        }
      }
    } catch {
      recoveryError = 'Saved activity could not be recovered; existing records were preserved.';
    }
    pending = outboxUnion(recovered);
    persist();
  }
  notify();

  return {
    add(intervals, end) {
      const additions = outboxInput(intervals, end); // Validate atomically before mutation.
      pending = outboxUnion(pending.concat(additions));
      persist();
      notify();
    },
    getBatch() {
      const batch = [];
      for (const [start, end] of pending) {
        let cursor = start;
        while (cursor < end && batch.length < OUTBOX_MAX_BATCH) {
          const until = Math.min(end, cursor + OUTBOX_MAX_INTERVAL);
          batch.push({ start: cursor, end: until });
          cursor = until;
        }
        if (batch.length === OUTBOX_MAX_BATCH) break;
      }
      return batch;
    },
    ack(intervals) {
      const acknowledged = outboxUnion(outboxInput(intervals));
      pending = outboxSubtract(pending, acknowledged);
      persist();
      notify();
    },
    getPending,
    pendingIntervals: getPending,
    pendingMs,
    getState,
  };
}
