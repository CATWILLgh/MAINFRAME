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
const record = pending => JSON.stringify({ version: 1, pending });
function fixture({ scope = 'opaque-profile', id = 'random-instance', storage = new MemoryStorage(), ...options } = {}) {
  return { storage, outbox: createOutbox({ storage, scope, id, ...options }) };
}
function keyFor(storage, id) {
  return [...storage.data.keys()].find(key => key.endsWith(`:${encodeURIComponent(id)}`));
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

test('normalizes unordered overlap/adjacency and returns detached copies', () => {
  const { outbox, storage } = fixture();
  outbox.add([pair(20, 30), pair(0, 10), pair(10, 22), pair(50, 60)]);
  assert.deepEqual(outbox.getPending(), [pair(0, 30), pair(50, 60)]);
  assert.equal(outbox.pendingMs(), 40);
  assert.deepEqual(outbox.getState(), { pendingMs: 40, pendingCount: 2, durable: true, error: null, recoveryError: null });
  assert.deepEqual(JSON.parse(storage.getItem(keyFor(storage, 'random-instance'))), { version: 1, pending: [[0, 30], [50, 60]] });
  const view = outbox.getPending(); view[0].start = 999; view.push(pair(100, 200));
  const batch = outbox.getBatch(); batch[0].end = 1;
  const state = outbox.getState(); state.pendingMs = 123;
  assert.equal(outbox.pendingMs(), 40);
  assert.deepEqual(outbox.pendingIntervals(), [pair(0, 30), pair(50, 60)]);
});

test('100,000 frequent events retain exact totals and synchronously persist every add', () => {
  const { outbox, storage } = fixture();
  const before = storage.writes;
  for (let index = 0; index < 100_000; index++) outbox.add([pair(index * 7, (index + 1) * 7)]);
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
  // Old crash records intentionally survive: safe duplicate replay beats deleting
  // a foreign key that a live tab could update between compare and remove.
  assert.equal(JSON.parse(storage.getItem(keyFor(storage, 'first'))).pending.length, 2);
  assert.equal(createOutbox({ storage, scope: 'opaque-profile', id: 'third' }).pendingMs(), 390);
});

test('own-key reload after ACK sees no pending data; scoped profiles stay isolated', () => {
  const { storage, outbox } = fixture({ id: 'same-id', scope: 'profile:A' });
  outbox.add(10, 20); outbox.ack(outbox.getBatch());
  assert.equal(createOutbox({ storage, scope: 'profile:A', id: 'same-id' }).pendingMs(), 0);
  outbox.add(50, 70);
  const other = createOutbox({ storage, scope: 'profile:B', id: 'fresh' });
  assert.equal(other.pendingMs(), 0);
  assert.equal(storage.data.size, 2);
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
  assert.equal(storage.getItem(originalKey), raw);
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

test('malformed scoped records are preserved verbatim, warned, and never partially restored', () => {
  const { storage, outbox } = fixture({ id: 'bad' });
  const key = keyFor(storage, 'bad');
  const invalid = [
    '{ broken', 'null', '[]', record([[1, 4], [5, 5]]), record([[1, 4], [5, Infinity]]),
    JSON.stringify({ version: 2, pending: [[1, 10]] }),
    JSON.stringify({ version: 1, pending: [[1, 10]], content: 'never persist content' }),
    record([['1', 10]]), record([[-1, 10]]), record([[0, 8_640_000_000_000_001]]),
  ];
  for (let index = 0; index < invalid.length; index++) {
    const raw = invalid[index]; storage.setItem(key, raw);
    const restored = createOutbox({ storage, scope: 'opaque-profile', id: `valid-${index}` });
    assert.equal(restored.pendingMs(), 0);
    assert.ok(restored.getState().recoveryError);
    restored.add(20, 30);
    assert.equal(storage.getItem(key), raw);
    restored.ack(restored.getBatch());
  }
  // Also preserve malformed own-id collision instead of overwriting evidence.
  storage.setItem(key, invalid[0]);
  const collision = createOutbox({ storage, scope: 'opaque-profile', id: 'bad' });
  collision.add(500, 510);
  assert.equal(collision.pendingMs(), 10);
  assert.equal(collision.getState().durable, false);
  assert.equal(storage.getItem(key), invalid[0]);
  assert.equal(outbox.pendingMs(), 0);
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

test('two live instances: recovery and ACK never change another instance record', () => {
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
  storage.removeItem = () => { throw new Error('Foreign records must never be deleted'); };
  const second = createOutbox({ storage, scope: 'opaque-profile', id: 'second' });
  assert.equal(second.pendingMs(), 100); // Only its recovery snapshot.
  assert.deepEqual(JSON.parse(get(firstKey)).pending, [[0, 200]]);
  const firstSent = first.getBatch();
  const secondSent = second.getBatch();
  first.add(150, 300);
  second.add(90, 180);
  second.ack(secondSent);
  assert.deepEqual(second.getPending(), [pair(100, 180)]);
  assert.deepEqual(JSON.parse(get(firstKey)).pending, [[0, 300]]);
  const secondKey = keyFor(storage, 'second');
  const secondRaw = get(secondKey);
  first.ack(firstSent);
  assert.deepEqual(first.getPending(), [pair(200, 300)]);
  assert.equal(get(secondKey), secondRaw);
  const recovered = createOutbox({ storage, scope: 'opaque-profile', id: 'third' });
  assert.deepEqual(recovered.getPending(), [pair(100, 180), pair(200, 300)]);
});

test('recovery persists its snapshot before a live original can ACK and close', () => {
  const { storage, outbox: first } = fixture({ id: 'first' });
  first.add(0, 500);
  let recoverPersisted = false;
  const set = storage.setItem.bind(storage);
  storage.setItem = (key, value) => {
    set(key, value);
    if (key.endsWith(':second') && !recoverPersisted) {
      recoverPersisted = true;
      first.ack(first.getBatch());
    }
  };
  const second = createOutbox({ storage, scope: 'opaque-profile', id: 'second' });
  assert.equal(second.pendingMs(), 500);
  assert.equal(first.pendingMs(), 0);
  assert.equal(createOutbox({ storage, scope: 'opaque-profile', id: 'third' }).pendingMs(), 500);
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
