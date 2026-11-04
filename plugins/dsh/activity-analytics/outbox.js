/* Pure browser-compatible, synchronous interval outbox. No ambient storage/DOM access.
 *
 * The caller supplies an opaque, authenticated profile scope and a fresh random
 * instance id (e.g. crypto.randomUUID()). Only those opaque identifiers occur in
 * keys; values contain a version and numeric half-open epoch-ms intervals.
 *
 * Every add/ACK writes the complete union to this instance's key. Recovery copies
 * all valid scoped snapshots into that union BEFORE reporting state. Foreign keys
 * are deliberately never changed/deleted: Storage has no atomic compare/delete,
 * so even checking unchanged raw text before deletion could lose a live tab's
 * intervening write. This trades stale records/replays for strict cross-tab safety.
 * Host interval union makes repeated delivery idempotent. There is no queue cap,
 * eviction, timer, or dependency on storage events. Quota/other storage failures
 * retain memory and report volatile state; a later add/ACK retries persistence.
 */

const OUTBOX_PREFIX = 'activity-analytics:outbox:v1:';
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

function outboxRecord(raw) {
  const value = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value) || value.version !== 1 ||
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
  const ownKey = prefix === null ? null : `${prefix}${encodeURIComponent(id)}`;
  let pending = [];
  let durable = false;
  let error = null;
  let recoveryError = null;
  let writable = true;

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
    if (!writable) {
      error = 'An existing unreadable or malformed outbox record was preserved; new activity is only in memory.';
      return;
    }
    try {
      if (!storage || typeof storage.setItem !== 'function') throw new TypeError('Unavailable storage.');
      storage.setItem(ownKey, JSON.stringify({ version: 1, pending }));
      durable = true;
      error = null;
    } catch {
      error = 'Activity storage is unavailable; unsynced activity is only in memory.';
    }
  }

  if (scope !== null) {
    try {
      if (!storage || typeof storage.getItem !== 'function' || typeof storage.key !== 'function' ||
          typeof storage.setItem !== 'function') throw new TypeError('Unavailable storage.');
      // Snapshot the key directory first. Other tabs may change values throughout
      // recovery; each value is only ever read, never overwritten under their id.
      const keys = new Set();
      const count = storage.length;
      if (!Number.isSafeInteger(count) || count < 0) throw new TypeError('Unavailable storage directory.');
      for (let index = 0; index < count; index++) {
        const key = storage.key(index);
        if (typeof key === 'string' && key.startsWith(prefix)) keys.add(key);
      }
      // Also check our id directly, so a collision with malformed data is never
      // overwritten even if a concurrent directory change skipped its key.
      keys.add(ownKey);
      const recovered = [];
      for (const key of keys) {
        let raw;
        try { raw = storage.getItem(key); } catch {
          recoveryError = 'Some saved activity could not be recovered; existing records were preserved.';
          if (key === ownKey) writable = false;
          continue;
        }
        if (raw === null) continue;
        try { for (const interval of outboxRecord(raw)) recovered.push(interval); } catch {
          recoveryError = 'A malformed saved activity record was preserved and could not be recovered.';
          if (key === ownKey) writable = false;
        }
      }
      pending = outboxUnion(recovered);
    } catch {
      recoveryError = 'Saved activity could not be recovered; existing records were preserved.';
      // A failed directory/getter can hide a malformed own record. Do not risk
      // replacing it. The caller can retry creation with a fresh random id.
      writable = false;
    }
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
