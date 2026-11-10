import test from 'node:test';
import assert from 'node:assert/strict';
import { createOutbox } from './outbox.js';

class MemoryStorage {
  data = new Map();
  writes = 0;
  get length() { return this.data.size; }
  key(index) { return [...this.data.keys()][index] ?? null; }
  getItem(key) { return this.data.get(String(key)) ?? null; }
  setItem(key, value) { this.writes++; this.data.set(String(key), String(value)); }
  removeItem(key) { this.data.delete(String(key)); }
}
const pair = (start, end) => ({ start, end });
const record = (pending, version = 2) => JSON.stringify({ version, pending });
const v2Key = (id, sequence, scope = 'opaque-profile') =>
  `activity-analytics:outbox:v2:${encodeURIComponent(scope)}:${encodeURIComponent(id)}:${sequence}`;
const v1Key = (id, scope = 'opaque-profile') =>
  `activity-analytics:outbox:v1:${encodeURIComponent(scope)}:${encodeURIComponent(id)}`;
function fixture({ scope = 'opaque-profile', id = 'random-instance', storage = new MemoryStorage(), ...options } = {}) {
  return { storage, outbox: createOutbox({ storage, scope, id, ...options }) };
}
function keyFor(storage, id) {
  return [...storage.data.keys()].find(key => key.startsWith('activity-analytics:outbox:v2:') &&
    key.split(':').at(-2) === encodeURIComponent(id));
}
function points(intervals) {
  const result = new Set();
  for (const { start, end } of intervals) for (let point = start; point < end; point++) result.add(point);
  return result;
}
function random(seed) {
  let state = seed >>> 0;
  return max => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state % max; };
}

test('1,000 crash/reload+ACK cycles leave no stale snapshots or later replay', () => {
  const storage = new MemoryStorage();
  for (let index = 0; index < 1_000; index++) {
    const box = createOutbox({ storage, scope: 'scope', id: `writer-${index}` });
    assert.equal(storage.length, 0);
    box.add(index * 10, index * 10 + 5);
    const reloaded = createOutbox({ storage, scope: 'scope', id: `reloaded-${index}` });
    assert.deepEqual(reloaded.getPending(), [pair(index * 10, index * 10 + 5)]);
    reloaded.ack(reloaded.getBatch());
    assert.equal(storage.length, 0);
    const afterACK = createOutbox({ storage, scope: 'scope', id: `after-ack-${index}` });
    assert.deepEqual(afterACK.getBatch(), []);
    assert.equal(storage.length, 0);
  }
});

test('failed captured snapshot removal preserves replay and retries after ACK', () => {
  const { outbox, storage } = fixture({ id: 'owner' });
  outbox.add(10, 20);
  const ownKey = keyFor(storage, 'owner');
  const remove = storage.removeItem.bind(storage);
  storage.removeItem = () => { throw new Error('synthetic private storage failure'); };
  outbox.ack(outbox.getBatch());
  assert.equal(outbox.pendingMs(), 0);
  assert.equal(outbox.getState().durable, true); // Only duplicate cleanup failed; Host has ACKed.
  assert.ok(outbox.getState().error);
  assert.equal(storage.getItem(ownKey), record([[10, 20]]));
  storage.removeItem = remove;
  outbox.add([]);
  assert.equal(outbox.getState().durable, true);
  assert.equal(storage.getItem(ownKey), null);
});

test('normalizes unordered overlap/adjacency and returns detached copies', () => {
  const { outbox, storage } = fixture();
  outbox.add([pair(20, 30), pair(0, 10), pair(10, 22), pair(50, 60)]);
  assert.deepEqual(outbox.getPending(), [pair(0, 30), pair(50, 60)]);
  assert.equal(outbox.pendingMs(), 40);
  assert.deepEqual(outbox.getState(), { pendingMs: 40, pendingCount: 2, durable: true, error: null, recoveryError: null });
  assert.deepEqual(JSON.parse(storage.getItem(keyFor(storage, 'random-instance'))), { version: 2, pending: [[0, 30], [50, 60]] });
  const view = outbox.getPending(); view[0].start = 999; view.push(pair(100, 200));
  const batch = outbox.getBatch(); batch[0].end = 1;
  const state = outbox.getState(); state.pendingMs = 123;
  assert.equal(outbox.pendingMs(), 40);
  assert.deepEqual(outbox.pendingIntervals(), [pair(0, 30), pair(50, 60)]);
});

test('100,000 frequent events retain exact totals and synchronously persist every add', () => {
  const { outbox, storage } = fixture();
  const before = storage.writes;
  let priorKey = null;
  for (let index = 0; index < 100_000; index++) {
    outbox.add([pair(index * 7, (index + 1) * 7)]);
    assert.equal(storage.length, 1);
    const key = keyFor(storage, 'random-instance');
    assert.notEqual(key, priorKey);
    assert.equal(Number(key.split(':').at(-1)), index + 1);
    priorKey = key;
  }
  assert.equal(outbox.pendingMs(), 700_000);
  assert.deepEqual(outbox.getPending(), [pair(0, 700_000)]);
  assert.equal(storage.writes - before, 100_000);
  assert.equal(outbox.getBatch().length, 24);
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'after-crash' });
  assert.equal(restored.pendingMs(), 700_000);
});

test('backlogs larger than 256 segments drain in bounded batches without truncation', () => {
  const { outbox } = fixture();
  const total = 30_000 * (256 * 3 + 7) + 1234;
  outbox.add(0, total);
  let acknowledged = 0;
  let batches = 0;
  while (outbox.pendingMs()) {
    const batch = outbox.getBatch();
    assert.ok(batch.length >= 1 && batch.length <= 256);
    for (const interval of batch) {
      assert.ok(interval.end - interval.start > 0 && interval.end - interval.start <= 30_000);
      acknowledged += interval.end - interval.start;
    }
    if (!batches) assert.equal(batch.length, 256);
    outbox.ack(batch); batches++;
  }
  assert.equal(batches, 4);
  assert.equal(acknowledged, total);
  assert.deepEqual(outbox.getBatch(), []);
});

test('more than 256 disjoint intervals are also retained and drained', () => {
  const { outbox } = fixture();
  outbox.add(Array.from({ length: 1_000 }, (_, index) => pair(index * 10, index * 10 + 3)));
  assert.equal(outbox.getState().pendingCount, 1_000);
  let total = 0;
  while (outbox.pendingMs()) {
    const batch = outbox.getBatch();
    total += batch.reduce((sum, item) => sum + item.end - item.start, 0);
    outbox.ack(batch);
  }
  assert.equal(total, 3_000);
});

test('ACK subtracts exact in-flight ranges, preserving overlapping appended tails and holes', () => {
  const { outbox } = fixture();
  outbox.add([pair(100, 200), pair(300, 400)]);
  const sent = outbox.getBatch();
  outbox.add([pair(50, 150), pair(175, 350), pair(390, 500)]);
  outbox.ack(sent);
  assert.deepEqual(outbox.getPending(), [pair(50, 100), pair(200, 300), pair(400, 500)]);
  outbox.ack(sent); // Repeated ACK is harmless.
  assert.equal(outbox.pendingMs(), 250);
  outbox.ack([pair(450, 550), pair(75, 225)]);
  assert.deepEqual(outbox.getPending(), [pair(50, 75), pair(225, 300), pair(400, 450)]);
});

test('randomized union/subtraction matches independent point-set oracle', () => {
  for (let seed = 0; seed < 40; seed++) {
    const rng = random(seed);
    const outbox = createOutbox({ id: `memory-${seed}` });
    const oracle = new Set();
    for (let operation = 0; operation < 300; operation++) {
      const intervals = Array.from({ length: rng(5) + 1 }, () => {
        const start = rng(200); return pair(start, start + rng(35) + 1);
      });
      if (rng(3)) {
        outbox.add(intervals);
        for (const point of points(intervals)) oracle.add(point);
      } else {
        outbox.ack(intervals);
        for (const point of points(intervals)) oracle.delete(point);
      }
      assert.deepEqual(points(outbox.getPending()), oracle, `seed ${seed}, operation ${operation}`);
      assert.equal(outbox.pendingMs(), oracle.size);
      const union = outbox.getPending();
      for (let index = 1; index < union.length; index++) assert.ok(union[index - 1].end < union[index].start);
    }
  }
});

test('reload/crash before ACK replays durable intervals and Host union makes duplicate sends harmless', () => {
  const { outbox: first, storage } = fixture({ id: 'first' });
  first.add([pair(10, 100), pair(200, 500)]);
  const sentBeforeCrash = first.getBatch();
  const host = points(sentBeforeCrash); // Host committed, but browser did not receive ACK.
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'restored' });
  assert.deepEqual(restored.getBatch(), sentBeforeCrash);
  for (const point of points(restored.getBatch())) host.add(point);
  assert.equal(host.size, 390);
  restored.ack(restored.getBatch());
  assert.equal(restored.pendingMs(), 0);
  assert.equal(storage.length, 0);
  assert.equal(createOutbox({ storage, scope: 'opaque-profile', id: 'third' }).pendingMs(), 0);
});

test('fresh reload after ACK sees no pending data; scoped profiles stay isolated', () => {
  const { storage, outbox } = fixture({ id: 'owner', scope: 'profile:A' });
  outbox.add(10, 20); outbox.ack(outbox.getBatch());
  assert.equal(createOutbox({ storage, scope: 'profile:A', id: 'fresh-reload' }).pendingMs(), 0);
  outbox.add(50, 70);
  const other = createOutbox({ storage, scope: 'profile:B', id: 'fresh' });
  assert.equal(other.pendingMs(), 0);
  assert.equal(storage.data.size, 1);
  assert.equal(createOutbox({ storage, scope: 'profile:A:extra', id: 'fresh' }).pendingMs(), 0);
});

test('quota failure never discards memory and later successful write restores durability', () => {
  const storage = new MemoryStorage();
  let quota = false;
  const write = storage.setItem.bind(storage);
  storage.setItem = (key, value) => { if (quota) throw new Error('private quota details'); write(key, value); };
  const states = [];
  const outbox = createOutbox({ storage, scope: 'scope', id: 'random', onState: state => states.push(state) });
  outbox.add(0, 100);
  quota = true;
  outbox.add(100, 300);
  assert.equal(outbox.pendingMs(), 300);
  assert.equal(outbox.getState().durable, false);
  assert.ok(outbox.getState().error);
  assert.ok(!outbox.getState().error.includes('private'));
  const batch = outbox.getBatch();
  outbox.add(250, 400);
  outbox.ack(batch);
  assert.deepEqual(outbox.getPending(), [pair(300, 400)]);
  assert.equal(outbox.getState().durable, false);
  quota = false;
  outbox.add([]); // Retry includes the full current memory union.
  assert.equal(outbox.getState().durable, true);
  assert.equal(outbox.getState().error, null);
  assert.deepEqual(JSON.parse(storage.getItem(keyFor(storage, 'random'))).pending, [[300, 400]]);
  assert.equal(states[0].pendingMs, 0);
  assert.equal(states.at(-1).pendingMs, 100);
});

test('failed recovery copy leaves original durable snapshots and recovered memory intact', () => {
  const { storage, outbox: original } = fixture({ id: 'original' });
  original.add(100, 900);
  const originalKey = keyFor(storage, 'original');
  const raw = storage.getItem(originalKey);
  const write = storage.setItem.bind(storage);
  storage.setItem = () => { throw new Error('quota'); };
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'recovering' });
  assert.equal(restored.pendingMs(), 800);
  assert.equal(restored.getState().durable, false);
  assert.ok(restored.getState().error);
  assert.equal(storage.getItem(originalKey), raw);
  restored.add(850, 1000);
  assert.equal(restored.pendingMs(), 900);
  assert.equal(storage.getItem(originalKey), raw);
  storage.setItem = write;
  restored.add([]);
  assert.equal(restored.getState().durable, true);
  assert.equal(storage.getItem(originalKey), null);
  assert.equal(storage.length, 1);
  assert.equal(createOutbox({ storage, scope: 'opaque-profile', id: 'next' }).pendingMs(), 900);
});

test('storage unavailable, throwing accessors/methods, and pre-auth memory mode are contained', () => {
  const touching = new Proxy({}, { get() { throw new Error('Do not touch storage before authentication'); } });
  const memory = createOutbox({ storage: touching, scope: null, id: 'preauth' });
  memory.add(1, 11);
  assert.equal(memory.pendingMs(), 10);
  assert.deepEqual(memory.getState(), { pendingMs: 10, pendingCount: 1, durable: false, error: null, recoveryError: null });
  const unavailable = [null, touching, {}, {
    length: 0, key() { return null; }, getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); },
  }];
  for (const storage of unavailable) {
    const box = createOutbox({ storage, scope: 'scope', id: 'unique' });
    box.add(100, 150);
    assert.equal(box.pendingMs(), 50);
    assert.equal(box.getState().durable, false);
    assert.ok(box.getState().error || box.getState().recoveryError);
    box.ack([pair(110, 120)]);
    assert.equal(box.pendingMs(), 40);
  }
});

test('malformed v1/v2 records are isolated, preserved verbatim, and never partially restored', () => {
  for (const version of [1, 2]) {
    const storage = new MemoryStorage();
    const key = version === 1 ? v1Key('bad') : v2Key('bad', 1);
    const invalid = [
      '{ broken', 'null', '[]', record([[1, 4], [5, 5]], version), record([[1, 4], [5, Infinity]], version),
      record([[1, 10]], 3 - version),
      JSON.stringify({ version, pending: [[1, 10]], content: 'never persist content' }),
      record([['1', 10]], version), record([[-1, 10]], version), record([[0, 8_640_000_000_000_001]], version),
    ];
    for (let index = 0; index < invalid.length; index++) {
      const raw = invalid[index]; storage.setItem(key, raw);
      storage.setItem(v2Key(`good-${index}`, 1), record([[100, 110]]));
      const restored = createOutbox({ storage, scope: 'opaque-profile', id: `valid-${index}` });
      assert.deepEqual(restored.getPending(), [pair(100, 110)]);
      assert.ok(restored.getState().recoveryError);
      restored.add(20, 30);
      assert.equal(storage.getItem(key), raw);
      restored.ack(restored.getBatch());
      assert.equal(storage.length, 1);
    }
    // A malformed same-id collision is skipped, not overwritten or allowed to
    // block durable use of a different, fresh sequence.
    storage.setItem(key, invalid[0]);
    const collision = createOutbox({ storage, scope: 'opaque-profile', id: 'bad' });
    collision.add(500, 510);
    assert.equal(collision.pendingMs(), 10);
    assert.equal(collision.getState().durable, true);
    assert.equal(storage.getItem(key), invalid[0]);
  }
});

test('restore synchronously emits complete state, and observer exceptions do not lose samples', () => {
  const { storage, outbox } = fixture({ id: 'old' });
  outbox.add([pair(30, 80), pair(100, 150)]);
  const states = [];
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'new', onState: state => states.push(state) });
  assert.equal(states.length, 1);
  assert.deepEqual(states[0], { pendingMs: 100, pendingCount: 2, durable: true, error: null, recoveryError: null });
  restored.add(80, 100);
  assert.equal(states.at(-1).pendingMs, 120);
  const brokenObserver = createOutbox({ id: 'observer', onState() { throw new Error('UI'); } });
  brokenObserver.add(0, 100);
  assert.equal(brokenObserver.pendingMs(), 100);
});

test('live owner publishing a fresh snapshot during adoption preserves its uncaptured tail', () => {
  const { storage, outbox: first } = fixture({ id: 'first' });
  first.add(0, 100);
  const firstKey = keyFor(storage, 'first');
  let injected = false;
  const get = storage.getItem.bind(storage);
  storage.getItem = key => {
    const snapshot = get(key);
    if (key === firstKey && !injected) { injected = true; first.add(80, 200); }
    return snapshot;
  };
  const second = createOutbox({ storage, scope: 'opaque-profile', id: 'second' });
  assert.equal(second.pendingMs(), 100); // Only its captured recovery snapshot.
  assert.notEqual(keyFor(storage, 'first'), firstKey);
  assert.deepEqual(JSON.parse(get(keyFor(storage, 'first'))).pending, [[0, 200]]);
  const firstSent = first.getBatch();
  const secondSent = second.getBatch();
  first.add(150, 300);
  second.add(90, 180);
  second.ack(secondSent);
  assert.deepEqual(second.getPending(), [pair(100, 180)]);
  assert.deepEqual(JSON.parse(get(keyFor(storage, 'first'))).pending, [[0, 300]]);
  const secondKey = keyFor(storage, 'second');
  const secondRaw = get(secondKey);
  first.ack(firstSent);
  assert.deepEqual(first.getPending(), [pair(200, 300)]);
  assert.equal(get(secondKey), secondRaw);
  const recovered = createOutbox({ storage, scope: 'opaque-profile', id: 'third' });
  assert.deepEqual(recovered.getPending(), [pair(100, 180), pair(200, 300)]);
  assert.equal(storage.length, 1);
});

test('recovery persists its snapshot before a live original can ACK and close', () => {
  const { storage, outbox: first } = fixture({ id: 'first' });
  first.add(0, 500);
  let recoverPersisted = false;
  const set = storage.setItem.bind(storage);
  storage.setItem = (key, value) => {
    set(key, value);
    if (key === v2Key('second', 1) && !recoverPersisted) {
      recoverPersisted = true;
      first.ack(first.getBatch());
    }
  };
  const second = createOutbox({ storage, scope: 'opaque-profile', id: 'second' });
  assert.equal(second.pendingMs(), 500);
  assert.equal(first.pendingMs(), 0);
  assert.equal(createOutbox({ storage, scope: 'opaque-profile', id: 'third' }).pendingMs(), 500);
});

test('a live original keeps appending after another owner adopts and ACKs its snapshot', () => {
  const { storage, outbox: first } = fixture({ id: 'original' });
  first.add(0, 100);
  const retired = keyFor(storage, 'original');
  const adopter = createOutbox({ storage, scope: 'opaque-profile', id: 'adopter' });
  assert.equal(storage.getItem(retired), null);
  adopter.ack(adopter.getBatch());
  assert.equal(storage.length, 0);
  first.add(100, 200);
  assert.notEqual(keyFor(storage, 'original'), retired);
  first.ack([pair(0, 100)]);
  const reloaded = createOutbox({ storage, scope: 'opaque-profile', id: 'reload-live-tail' });
  assert.deepEqual(reloaded.getPending(), [pair(100, 200)]);
  reloaded.ack(reloaded.getBatch());
  assert.equal(storage.length, 0);
});

for (const interleave of ['cleanup read', 'remove']) {
  test(`fresh publication between recovery and ${interleave} never gets deleted by adoption`, () => {
    const { storage, outbox: first } = fixture({ id: 'first' });
    first.add(0, 100);
    const oldKey = keyFor(storage, 'first');
    const get = storage.getItem.bind(storage);
    const remove = storage.removeItem.bind(storage);
    let reads = 0;
    let injected = false;
    const publish = () => {
      if (injected) return;
      injected = true;
      first.add(100, 300);
    };
    storage.getItem = key => {
      const raw = get(key);
      if (key === oldKey && ++reads === 2 && interleave === 'cleanup read') publish();
      return raw;
    };
    storage.removeItem = key => {
      if (key === oldKey && interleave === 'remove') publish();
      remove(key);
    };
    const adopter = createOutbox({ storage, scope: 'opaque-profile', id: 'adopter' });
    assert.equal(injected, true);
    assert.deepEqual(adopter.getPending(), [pair(0, 100)]);
    assert.deepEqual(JSON.parse(get(keyFor(storage, 'first'))).pending, [[0, 300]]);
    adopter.ack(adopter.getBatch());
    first.ack([pair(0, 100)]);
    const reloaded = createOutbox({ storage, scope: 'opaque-profile', id: 'reloaded' });
    assert.deepEqual(reloaded.getPending(), [pair(100, 300)]);
    reloaded.ack(reloaded.getBatch());
    assert.equal(storage.length, 0);
  });
}

for (const committed of [false, true]) {
  test(`quota throw ${committed ? 'after' : 'before'} commit preserves sources/memory and consumes every key`, () => {
    const { storage, outbox } = fixture({ id: 'quota-owner' });
    outbox.add(0, 100);
    const source = keyFor(storage, 'quota-owner');
    const sourceRaw = storage.getItem(source);
    const set = storage.setItem.bind(storage);
    const remove = storage.removeItem.bind(storage);
    const attempts = [];
    const removals = [];
    let failing = true;
    storage.setItem = (key, raw) => {
      assert.equal(storage.getItem(key), null, 'immutable keys must not be overwritten');
      attempts.push(key);
      if (!failing || committed) set(key, raw);
      if (failing) throw new Error('synthetic quota exception');
    };
    storage.removeItem = key => { removals.push(key); remove(key); };
    outbox.add(100, 200);
    outbox.add(200, 300);
    assert.equal(outbox.pendingMs(), 300);
    assert.equal(outbox.getState().durable, false);
    assert.ok(outbox.getState().error);
    assert.equal(storage.getItem(source), sourceRaw);
    assert.deepEqual(removals, []);
    assert.equal(storage.length, committed ? 3 : 1);
    const crashCopy = copyStorage(storage);
    const afterCrash = createOutbox({ storage: crashCopy, scope: 'opaque-profile', id: 'quota-crash' });
    assert.deepEqual(afterCrash.getPending(), [pair(0, committed ? 300 : 100)]);
    afterCrash.ack(afterCrash.getBatch());
    assert.equal(crashCopy.length, 0);
    failing = false;
    outbox.add([]);
    assert.deepEqual(attempts, [v2Key('quota-owner', 2), v2Key('quota-owner', 3), v2Key('quota-owner', 4)]);
    assert.equal(storage.length, 1);
    assert.equal(outbox.getState().durable, true);
    assert.equal(storage.getItem(v2Key('quota-owner', 4)), record([[0, 300]]));
    outbox.ack(outbox.getBatch());
    assert.equal(storage.length, 0);
    outbox.add(400, 500);
    assert.equal(storage.getItem(v2Key('quota-owner', 5)), record([[400, 500]]));
    assert.equal(new Set(attempts).size, attempts.length);
  });

  test(`partial ACK residual ${committed ? 'post' : 'pre'}-commit failure preserves appended tails until retry`, () => {
    const { storage, outbox } = fixture({ id: 'ack-owner' });
    outbox.add(100, 200);
    const sent = outbox.getBatch();
    outbox.add([pair(50, 125), pair(175, 300)]);
    const source = keyFor(storage, 'ack-owner');
    const raw = storage.getItem(source);
    const set = storage.setItem.bind(storage);
    storage.setItem = (key, value) => {
      if (committed) set(key, value);
      throw new Error('synthetic failure');
    };
    outbox.ack(sent);
    assert.deepEqual(outbox.getPending(), [pair(50, 100), pair(200, 300)]);
    assert.equal(outbox.getState().durable, false);
    assert.equal(storage.getItem(source), raw);
    storage.setItem = set;
    outbox.add([]);
    assert.equal(storage.length, 1);
    const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'ack-reload' });
    assert.deepEqual(restored.getPending(), [pair(50, 100), pair(200, 300)]);
    restored.ack(restored.getBatch());
    assert.equal(storage.length, 0);
  });
}

function copyStorage(storage) {
  const copy = new MemoryStorage();
  copy.data = new Map(storage.data);
  return copy;
}

test('crashes before/after replacement commit and cleanup recover every durable interval', () => {
  const { storage, outbox } = fixture({ id: 'writer' });
  outbox.add(0, 100);
  const set = storage.setItem.bind(storage);
  const remove = storage.removeItem.bind(storage);
  const checkpoints = [];
  storage.setItem = (key, raw) => {
    checkpoints.push({ label: 'before commit', storage: copyStorage(storage), expected: [pair(0, 100)] });
    set(key, raw);
    checkpoints.push({ label: 'after commit', storage: copyStorage(storage), expected: [pair(0, 200)] });
  };
  storage.removeItem = key => {
    assert.equal(storage.length, 2, 'replacement must exist before source removal');
    checkpoints.push({ label: 'before cleanup', storage: copyStorage(storage), expected: [pair(0, 200)] });
    remove(key);
    checkpoints.push({ label: 'after cleanup', storage: copyStorage(storage), expected: [pair(0, 200)] });
  };
  outbox.add(100, 200);
  assert.equal(checkpoints.length, 4);
  for (const checkpoint of checkpoints) {
    const restored = createOutbox({ storage: checkpoint.storage, scope: 'opaque-profile', id: 'after-crash' });
    assert.deepEqual(restored.getPending(), checkpoint.expected, checkpoint.label);
    assert.equal(checkpoint.storage.length, 1);
    restored.ack(restored.getBatch());
    assert.equal(checkpoint.storage.length, 0);
  }
});

test('adoption copies the complete union before any captured source deletion, including crash cut points', () => {
  const storage = new MemoryStorage();
  storage.setItem(v2Key('one', 1), record([[0, 100]]));
  storage.setItem(v2Key('two', 1), record([[200, 300]]));
  const set = storage.setItem.bind(storage);
  const remove = storage.removeItem.bind(storage);
  const checkpoints = [copyStorage(storage)];
  storage.setItem = (key, raw) => { set(key, raw); checkpoints.push(copyStorage(storage)); };
  storage.removeItem = key => {
    assert.equal(storage.getItem(v2Key('adopter', 1)), record([[0, 100], [200, 300]]));
    checkpoints.push(copyStorage(storage));
    remove(key);
    checkpoints.push(copyStorage(storage));
  };
  const adopted = createOutbox({ storage, scope: 'opaque-profile', id: 'adopter' });
  assert.deepEqual(adopted.getPending(), [pair(0, 100), pair(200, 300)]);
  assert.equal(checkpoints.length, 6);
  for (const copy of checkpoints) {
    const restored = createOutbox({ storage: copy, scope: 'opaque-profile', id: 'crash-recovery' });
    assert.deepEqual(restored.getPending(), adopted.getPending());
    assert.equal(copy.length, 1);
  }
});

test('successful partial ACK publishes residual before deleting the appended full snapshot', () => {
  const { storage, outbox } = fixture({ id: 'partial' });
  outbox.add(0, 100);
  const sent = outbox.getBatch();
  outbox.add(90, 200);
  const source = keyFor(storage, 'partial');
  const remove = storage.removeItem.bind(storage);
  storage.removeItem = key => {
    assert.equal(key, source);
    assert.equal(storage.getItem(v2Key('partial', 3)), record([[100, 200]]));
    remove(key);
  };
  outbox.ack(sent);
  storage.removeItem = remove;
  assert.equal(storage.length, 1);
  assert.deepEqual(createOutbox({ storage, scope: 'opaque-profile', id: 'partial-reload' }).getPending(), [pair(100, 200)]);
});

test('failed removal retries only captured records and preserves newer live-owner publications', () => {
  const { storage, outbox: first } = fixture({ id: 'first' });
  first.add(0, 100);
  const oldKey = keyFor(storage, 'first');
  const remove = storage.removeItem.bind(storage);
  storage.removeItem = key => {
    if (key === oldKey) throw new Error('synthetic remove failure');
    remove(key);
  };
  const adopter = createOutbox({ storage, scope: 'opaque-profile', id: 'adopter' });
  assert.equal(adopter.getState().durable, true); // Replacement is durable despite deferred cleanup.
  assert.match(adopter.getState().error, /retained/);
  first.add(100, 300);
  const freshKey = v2Key('first', 2);
  const freshRaw = storage.getItem(freshKey);
  storage.removeItem = remove;
  adopter.ack(adopter.getBatch());
  assert.equal(storage.getItem(oldKey), null);
  assert.equal(storage.getItem(freshKey), freshRaw);
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'retry-reload' });
  assert.deepEqual(restored.getPending(), [pair(0, 300)]);
  restored.ack(restored.getBatch());
  assert.equal(storage.length, 0);
});

test('legacy v1 is strictly read-only and replayable even when an old tab mutates during recovery', () => {
  const storage = new MemoryStorage();
  const legacy = v1Key('old-tab');
  const foreign = v1Key('other-profile', 'different-scope');
  storage.setItem(legacy, record([[0, 100]], 1));
  storage.setItem(foreign, record([[900, 1000]], 1));
  storage.setItem(v2Key('old-v2', 1), record([[300, 400]]));
  const get = storage.getItem.bind(storage);
  const set = storage.setItem.bind(storage);
  const remove = storage.removeItem.bind(storage);
  let mutated = false;
  storage.getItem = key => {
    const raw = get(key);
    if (key === legacy && !mutated) {
      mutated = true;
      set(legacy, record([[0, 200]], 1)); // A legacy writer mutates its own key.
    }
    return raw;
  };
  storage.setItem = (key, raw) => { assert.ok(!key.includes(':v1:')); set(key, raw); };
  storage.removeItem = key => { assert.ok(!key.includes(':v1:')); remove(key); };
  const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'new-v2' });
  assert.deepEqual(outbox.getPending(), [pair(0, 100), pair(300, 400)]);
  assert.equal(storage.getItem(v2Key('old-v2', 1)), null);
  outbox.ack(outbox.getBatch());
  assert.equal(storage.getItem(legacy), record([[0, 200]], 1));
  assert.equal(storage.getItem(foreign), record([[900, 1000]], 1));
  assert.equal(storage.length, 2);
  const replay = createOutbox({ storage, scope: 'opaque-profile', id: 'legacy-replay' });
  assert.deepEqual(replay.getPending(), [pair(0, 200)]);
  replay.ack(replay.getBatch());
  assert.equal(storage.length, 2);
});

test('no Web Locks, navigator, timers, or ambient storage are needed for synchronous cleanup', () => {
  const globals = ['navigator', 'localStorage', 'setTimeout', 'setInterval', 'addEventListener'];
  const previous = globals.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]);
  for (const name of globals) {
    Object.defineProperty(globalThis, name, { configurable: true, get() { throw new Error(`No ambient ${name} access`); } });
  }
  try {
    const { storage, outbox } = fixture({ id: 'no-locks' });
    outbox.add(10, 50);
    const recovered = createOutbox({ storage, scope: 'opaque-profile', id: 'no-locks-recovery' });
    assert.deepEqual(recovered.getBatch(), [pair(10, 50)]);
    assert.equal(storage.length, 1);
    recovered.ack(recovered.getBatch());
    assert.equal(storage.length, 0);
  } finally {
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
});

test('persisted same-id collisions are never overwritten or reused after retirement', () => {
  const storage = new MemoryStorage();
  storage.setItem(v2Key('collision', 1), record([[0, 100]]));
  storage.setItem(v2Key('collision', 4), record([[200, 300]]));
  const set = storage.setItem.bind(storage);
  const writes = [];
  storage.setItem = (key, raw) => {
    assert.equal(storage.getItem(key), null);
    writes.push(key);
    set(key, raw);
  };
  const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'collision' });
  assert.deepEqual(outbox.getPending(), [pair(0, 100), pair(200, 300)]);
  outbox.add(100, 200);
  outbox.ack(outbox.getBatch());
  outbox.add(500, 600);
  assert.deepEqual(writes, [v2Key('collision', 5), v2Key('collision', 6), v2Key('collision', 7)]);
  assert.equal(storage.length, 1);
});

test('a persisted collision missed by directory scanning is preserved by the write-time absence check', () => {
  const storage = new MemoryStorage();
  const collision = v2Key('same-id', 1);
  storage.setItem(collision, record([[10, 20]]));
  storage.key = () => null;
  const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'same-id' });
  outbox.add(30, 40);
  assert.equal(storage.getItem(collision), record([[10, 20]]));
  assert.equal(storage.getItem(v2Key('same-id', 2)), record([[30, 40]]));
  outbox.ack(outbox.getBatch());
  assert.equal(storage.getItem(collision), record([[10, 20]]));
});

test('unreadable records and malformed snapshot identities do not block valid recovery or get deleted', () => {
  const storage = new MemoryStorage();
  const unreadable = v2Key('unreadable', 1);
  const invalidKeys = [v2Key('invalid', 0), v2Key('invalid', '01'), v2Key('invalid', '1:extra'),
    v2Key('invalid', '9007199254740992'), v2Key('', 1)];
  storage.setItem(unreadable, record([[500, 600]]));
  for (const key of invalidKeys) storage.setItem(key, record([[700, 800]]));
  storage.setItem(v2Key('valid', 1), record([[0, 100]]));
  const get = storage.getItem.bind(storage);
  storage.getItem = key => {
    if (key === unreadable) throw new Error('synthetic read failure');
    return get(key);
  };
  const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'recover-readable' });
  assert.deepEqual(outbox.getPending(), [pair(0, 100)]);
  assert.equal(outbox.getState().durable, true);
  assert.ok(outbox.getState().recoveryError);
  outbox.ack(outbox.getBatch());
  for (const key of [unreadable, ...invalidKeys]) assert.notEqual(get(key), null);
  assert.equal(storage.length, 1 + invalidKeys.length);
});

test('empty recovery only retires valid empty v2 snapshots, without writing or touching legacy', () => {
  const storage = new MemoryStorage();
  storage.setItem(v2Key('empty', 1), record([]));
  storage.setItem(v1Key('empty-legacy'), record([], 1));
  storage.setItem(v2Key('malformed', 1), '{ malformed');
  const writes = storage.writes;
  const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'empty-recovery' });
  assert.equal(outbox.pendingMs(), 0);
  assert.equal(storage.getItem(v2Key('empty', 1)), null);
  assert.equal(storage.getItem(v1Key('empty-legacy')), record([], 1));
  assert.equal(storage.getItem(v2Key('malformed', 1)), '{ malformed');
  assert.equal(storage.writes, writes);
});

test('failed directory enumeration and skipped keys preserve records for a later complete recovery', () => {
  for (const fails of [true, false]) {
    const storage = new MemoryStorage();
    const source = v2Key('hidden', 1);
    storage.setItem(source, record([[0, 100]]));
    const key = storage.key.bind(storage);
    storage.key = () => { if (fails) throw new Error('synthetic directory failure'); return null; };
    const outbox = createOutbox({ storage, scope: 'opaque-profile', id: 'incomplete' });
    if (fails) assert.ok(outbox.getState().recoveryError);
    outbox.add(200, 300);
    outbox.ack(outbox.getBatch());
    assert.equal(storage.getItem(source), record([[0, 100]]));
    storage.key = key;
    const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'complete' });
    assert.deepEqual(restored.getPending(), [pair(0, 100)]);
    restored.ack(restored.getBatch());
    assert.equal(storage.length, 0);
  }
});

test('unreadable fresh candidate consumes its sequence without risking an overwrite', () => {
  const { storage, outbox } = fixture({ id: 'read-failure' });
  const get = storage.getItem.bind(storage);
  storage.getItem = key => {
    if (key === v2Key('read-failure', 1)) throw new Error('synthetic candidate read failure');
    return get(key);
  };
  outbox.add(0, 100);
  assert.equal(outbox.getState().durable, false);
  assert.equal(storage.writes, 0);
  outbox.add([]);
  assert.equal(outbox.getState().durable, true);
  assert.equal(get(v2Key('read-failure', 2)), record([[0, 100]]));
});

test('a malformed replacement of a captured record is preserved instead of retired', () => {
  const { storage, outbox } = fixture({ id: 'corruption' });
  outbox.add(0, 100);
  const source = keyFor(storage, 'corruption');
  storage.data.set(source, '{ corrupted');
  outbox.add(100, 200);
  assert.equal(storage.getItem(source), '{ corrupted');
  assert.ok(outbox.getState().recoveryError);
  outbox.ack(outbox.getBatch());
  assert.equal(storage.getItem(source), '{ corrupted');
  assert.equal(storage.length, 1);
});

for (const unreadableAttempt of [false, true]) {
  test(`100,000 failed precommit writes with ${unreadableAttempt ? 'unreadable' : 'absent'} candidates do not build a retirement journal`, () => {
    const { storage, outbox } = fixture({ id: 'sustained-quota' });
    outbox.add(0, 1);
    const source = keyFor(storage, 'sustained-quota');
    const get = storage.getItem.bind(storage);
    const set = storage.setItem.bind(storage);
    let failing = true;
    let reads = 0;
    let attempts = 0;
    let lastAttempt = null;
    const quotaError = new Error('synthetic quota');
    const readError = new Error('synthetic unavailable read');
    storage.getItem = key => {
      reads++;
      if (failing && unreadableAttempt && key === lastAttempt) throw readError;
      return get(key);
    };
    storage.setItem = (key, raw) => {
      if (!failing) return set(key, raw);
      attempts++;
      assert.equal(key, v2Key('sustained-quota', attempts + 1));
      lastAttempt = key;
      throw quotaError;
    };
    for (let index = 1; index <= 100_000; index++) outbox.add(index, index + 1);
    assert.equal(attempts, 100_000);
    assert.equal(reads, 200_000, 'read work stays constant per failed persistence');
    assert.equal(outbox.pendingMs(), 100_001);
    assert.equal(outbox.getState().durable, false);
    assert.equal(storage.length, 1);
    assert.equal(get(source), record([[0, 1]]));
    if (unreadableAttempt) assert.match(outbox.getState().recoveryError, /next recovery/);
    failing = false;
    reads = 0;
    outbox.add([]);
    assert.equal(reads, 2, 'retry inspects only one fresh key and the original successful source');
    assert.equal(outbox.getState().durable, true);
    assert.equal(storage.length, 1);
    assert.equal(get(v2Key('sustained-quota', 100_002)), record([[0, 100_001]]));
    outbox.ack(outbox.getBatch());
    assert.equal(storage.length, 0);
  });
}

test('ambiguous unreadable postcommit write stays intact for fresh recovery rather than growing a failure journal', () => {
  const { storage, outbox } = fixture({ id: 'ambiguous' });
  outbox.add(0, 100);
  const get = storage.getItem.bind(storage);
  const set = storage.setItem.bind(storage);
  let ambiguousKey = null;
  storage.setItem = (key, raw) => {
    set(key, raw);
    ambiguousKey = key;
    throw new Error('synthetic postcommit failure');
  };
  storage.getItem = key => {
    if (key === ambiguousKey) throw new Error('synthetic ambiguous read');
    return get(key);
  };
  outbox.add(100, 200);
  assert.equal(outbox.getState().durable, false);
  assert.match(outbox.getState().recoveryError, /next recovery/);
  assert.equal(storage.length, 2);
  storage.setItem = set;
  storage.getItem = get;
  outbox.add([]);
  assert.equal(storage.length, 2); // Confirmed source retired; unknown commit is untouched.
  outbox.ack(outbox.getBatch());
  assert.equal(storage.getItem(ambiguousKey), record([[0, 200]]));
  const restored = createOutbox({ storage, scope: 'opaque-profile', id: 'ambiguity-recovery' });
  assert.deepEqual(restored.getPending(), [pair(0, 200)]); // Harmless Host-idempotent replay.
  restored.ack(restored.getBatch());
  assert.equal(storage.length, 0);
});

test('cleanup read failure preserves the old snapshot and retries without losing replacement durability', () => {
  const { storage, outbox } = fixture({ id: 'cleanup-read' });
  outbox.add(0, 100);
  const source = keyFor(storage, 'cleanup-read');
  const get = storage.getItem.bind(storage);
  storage.getItem = key => {
    if (key === source) throw new Error('synthetic cleanup read failure');
    return get(key);
  };
  outbox.add(100, 200);
  assert.equal(outbox.getState().durable, true);
  assert.ok(outbox.getState().error);
  assert.equal(get(source), record([[0, 100]]));
  assert.equal(storage.length, 2);
  storage.getItem = get;
  outbox.ack(outbox.getBatch());
  assert.equal(storage.length, 0);
  assert.equal(outbox.getState().error, null);
});

test('removeItem throwing after deletion is retried harmlessly without ever recreating that key', () => {
  const { storage, outbox } = fixture({ id: 'remove-committed' });
  outbox.add(0, 100);
  const source = keyFor(storage, 'remove-committed');
  const remove = storage.removeItem.bind(storage);
  storage.removeItem = key => { remove(key); throw new Error('synthetic post-remove failure'); };
  outbox.add(100, 200);
  assert.equal(outbox.getState().durable, true);
  assert.ok(outbox.getState().error);
  assert.equal(storage.getItem(source), null);
  assert.equal(storage.length, 1);
  storage.removeItem = remove;
  outbox.add(200, 300);
  assert.equal(storage.getItem(source), null);
  assert.equal(storage.getItem(v2Key('remove-committed', 3)), record([[0, 300]]));
  assert.equal(storage.length, 1);
  assert.equal(outbox.getState().error, null);
});

test('validation is atomic and follows Host safe integer/date bounds', () => {
  const outbox = createOutbox({ id: 'validation' });
  outbox.add(0, 10);
  for (const value of [null, {}, [pair(10, 20), pair(30, 30)], [pair(1.5, 10)], [pair(-1, 1)],
    [pair(5, Infinity)], [pair(0, 8_640_000_000_000_001)], [[1]], [['1', 10]]]) {
    assert.throws(() => outbox.add(value), TypeError);
    assert.deepEqual(outbox.getPending(), [pair(0, 10)]);
    assert.throws(() => outbox.ack(value), TypeError);
    assert.deepEqual(outbox.getPending(), [pair(0, 10)]);
  }
  outbox.add([[8_639_999_999_999_999, 8_640_000_000_000_000]]);
  assert.equal(outbox.pendingMs(), 11);
  assert.throws(() => createOutbox({ id: '' }), TypeError);
  assert.throws(() => createOutbox({ id: 'x', scope: '' }), TypeError);
});
