import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { randomUUID } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { createHost, UI_PATH } from './index.js';

const source = await fs.readFile(new URL('client.js', import.meta.url), 'utf8');
const BASE = 1_800_000_000_000;

// All Host writes are confined to this fresh synthetic directory. Neither the
// real profile nor browser storage, history, credentials, or agent sessions enter
// the test. The VM receives only injected clocks and a Map-backed Storage.
async function deliveryFixture(t) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'activity-analytics-delivery-'));
  const listeners = new Map(), effects = [], reports = [];
  const browserPeer = {};
  let handler, wall = BASE, hostLag = 0, offline = false, failAfterCommit = false, closed = false;
  const calls = [];
  const storageValues = new Map();
  const storage = {
    get length() { return storageValues.size; },
    key(index) { return [...storageValues.keys()][index] ?? null; },
    getItem(key) { return storageValues.get(key) ?? null; },
    setItem(key, value) { storageValues.set(key, value); },
    removeItem(key) { storageValues.delete(key); },
  };
  const ctx = {
    agents: { list: () => [] },
    on(name, callback) { const list = listeners.get(name) ?? []; list.push(callback); listeners.set(name, list); },
    effect(callback) { effects.push(callback()); },
    connection: {
      browserPeer,
      admit: () => ({ peer: browserPeer }),
      fetch: { register(options) {
        assert.equal(options.path, UI_PATH);
        handler = options.fetch;
        return () => {};
      } },
    },
  };
  const store = await createHost(ctx, {
    directory,
    now: () => wall - hostLag,
    schedule: () => () => {},
    reportError: () => reports.push('Host storage failed'),
  });
  t.after(async () => {
    if (!closed) {
      listeners.clear();
      await Promise.all(effects.splice(0).map(cleanup => cleanup?.()));
      closed = true;
    }
    const absolute = path.resolve(directory);
    assert.equal(path.dirname(absolute), path.resolve(os.tmpdir()));
    assert.ok(path.basename(absolute).startsWith('activity-analytics-delivery-'));
    await fs.rm(absolute, { recursive: true, force: true });
  });
  async function request(body) {
    return handler(new Request(`http://localhost${UI_PATH}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-activity-analytics-ui': '1' },
      body: JSON.stringify(body),
    }));
  }
  function browser() {
    let mono = 0;
    const context = {
      window: {
        localStorage: storage,
        __ModuleLoader__: { load({ factory }) { factory(() => ({ createElement() {} })); } },
      },
      document: { visibilityState: 'visible', hasFocus: () => true },
      crypto: { randomUUID },
      Date: class extends Date { static now() { return wall; } },
      performance: { now: () => mono },
      AbortController, Intl, console,
      setTimeout: () => 1, clearTimeout() {},
      fetch: async (url, options) => {
        assert.equal(url, UI_PATH);
        assert.equal(options.headers['x-activity-analytics-ui'], '1');
        const body = JSON.parse(options.body);
        calls.push(body);
        if (body.op === 'activity' && offline) throw new Error('Synthetic offline transport');
        const response = await request(body);
        if (body.op === 'activity' && failAfterCommit && response.ok) {
          failAfterCommit = false;
          // The REAL handler has awaited its SQLite commit. Lose ONLY the HTTP
          // response, reproducing the unavoidable ambiguous-delivery boundary.
          throw new Error('Synthetic lost response AFTER Host committed');
        }
        return response;
      },
    };
    const marker = "return {inject:['slots','locale'],apply(ctx){";
    assert.ok(source.includes(marker));
    vm.runInNewContext(source.replace(marker, `globalThis.makeController=createController;${marker}`), context);
    const controller = context.makeController();
    controller.sample(true);
    return {
      controller,
      advance(ms) { wall += ms; mono += ms; },
    };
  }
  // An independent read-only connection proves data reached SQLite, not merely
  // the in-memory ActivityStore object or a fake fetch response.
  function committed() {
    const db = new DatabaseSync(path.join(directory, 'intervals.sqlite'), { readOnly: true });
    try {
      return { ...db.prepare('SELECT COUNT(*) AS count, COALESCE(SUM(end-start),0) AS total FROM user_intervals').get() };
    } finally { db.close(); }
  }
  return {
    store, browser, calls, storageValues, committed, reports,
    setOffline(value) { offline = value; },
    setHostLag(ms) { hostLag = ms; },
    setFailAfterCommit(value) { failAfterCommit = value; },
    async summary() {
      const response = await request({ op: 'summary', start: BASE, end: wall });
      assert.equal(response.status, 200);
      return response.json();
    },
  };
}

test('real SQLite commit + lost response survives offline reload and reclaims immutable snapshots without double counting', async t => {
  const f = await deliveryFixture(t);
  const original = f.browser();
  await original.controller.flush(); // Authenticated bootstrap, initially empty.
  original.advance(5_000);
  original.controller.sample(true);
  f.setFailAfterCommit(true);
  assert.equal(await original.controller.flush(), false);
  assert.equal(original.controller.getSnapshot().pendingMs, 5_000);
  assert.equal(original.controller.getSnapshot().syncError, true);
  assert.equal(original.controller.getSnapshot().durable, true);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });

  // Abrupt reload: abandon original controller without ACK or graceful flush.
  // A new VM/queue id recovers the old durable snapshot, including while offline.
  f.setOffline(true);
  const reloaded = f.browser();
  assert.equal(await reloaded.controller.flush(), false);
  assert.equal(reloaded.controller.getSnapshot().pendingMs, 5_000);
  assert.equal(reloaded.controller.getSnapshot().durable, true);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });
  assert.equal(f.storageValues.size, 1);
  for (const value of f.storageValues.values()) {
    const record = JSON.parse(value);
    assert.deepEqual(Object.keys(record).sort(), ['pending', 'version']);
    assert.equal(record.version, 2);
    for (const row of record.pending) assert.ok(row.length === 2 && row.every(Number.isSafeInteger));
  }
  f.setOffline(false);
  assert.equal(await reloaded.controller.flush(), true);
  assert.equal(reloaded.controller.getSnapshot().pendingMs, 0);
  assert.equal(reloaded.controller.getSnapshot().syncError, false);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });
  assert.equal((await f.summary()).userMs, 5_000);

  // Copy-first adoption retires immutable v2 crash records, and the genuine
  // Host ACK retires the replacement. Later reloads have nothing to replay.
  assert.equal(f.storageValues.size, 0);
  const delivered = f.calls.filter(body => body.op === 'activity').length;
  const replay = f.browser();
  assert.equal(await replay.controller.flush(), true);
  assert.equal(replay.controller.getSnapshot().pendingMs, 0);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });
  assert.equal((await f.summary()).userMs, 5_000);
  assert.equal(delivered, 3); // Lost response, offline attempt, successful retry.
  assert.equal(f.calls.filter(body => body.op === 'activity').length, delivered);
  assert.equal(f.storageValues.size, 0);
  assert.deepEqual(f.reports, []);
});

test('Host clock lag ACK retains clipped future tail until genuine persistence catches up', async t => {
  const f = await deliveryFixture(t);
  const client = f.browser();
  await client.controller.flush();
  client.advance(10_000);
  client.controller.sample(true);
  f.setHostLag(5_000);
  assert.equal(await client.controller.flush(), false);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });
  assert.equal(client.controller.getSnapshot().pendingMs, 5_000);
  assert.equal(client.controller.getSnapshot().syncError, true);
  assert.equal(client.controller.getSnapshot().durable, true);
  f.setHostLag(0);
  assert.equal(await client.controller.flush(), true);
  assert.deepEqual(f.committed(), { count: 1, total: 10_000 });
  assert.equal(client.controller.getSnapshot().pendingMs, 0);
  assert.equal(client.controller.getSnapshot().syncError, false);
  assert.equal((await f.summary()).userMs, 10_000);
  const activity = f.calls.filter(body => body.op === 'activity');
  assert.deepEqual(activity.map(body => body.intervals), [
    [{ start: BASE, end: BASE + 10_000 }],
    [{ start: BASE + 5_000, end: BASE + 10_000 }],
  ]);
  assert.deepEqual(f.reports, []);
});

test('live client resumes after another client adopts its snapshot; new tail survives genuine Host ACK', async t => {
  const f = await deliveryFixture(t);
  const live = f.browser();
  assert.equal(await live.controller.flush(), true);
  live.advance(5_000);
  live.controller.sample(true);
  const adopted = f.browser();
  f.setOffline(true);
  assert.equal(await adopted.controller.flush(), false);
  assert.equal(adopted.controller.getSnapshot().pendingMs, 5_000);
  assert.equal(f.storageValues.size, 1);

  // The original owner was only suspended, not dead. Its old key is gone,
  // but it must publish its new unacknowledged tail under a different key.
  live.advance(5_000);
  live.controller.sample(true);
  assert.equal(live.controller.getSnapshot().pendingMs, 10_000);
  assert.equal(f.storageValues.size, 2);
  f.setOffline(false);
  assert.equal(await adopted.controller.flush(), true);
  assert.deepEqual(f.committed(), { count: 1, total: 5_000 });
  assert.equal(f.storageValues.size, 1);
  assert.equal(await live.controller.flush(), true);
  assert.deepEqual(f.committed(), { count: 1, total: 10_000 });
  assert.equal(f.storageValues.size, 0);
  const sent = f.calls.filter(body => body.op === 'activity').length;
  assert.equal(await f.browser().controller.flush(), true);
  assert.equal(f.calls.filter(body => body.op === 'activity').length, sent);
  assert.deepEqual(f.reports, []);
});

test('generated client drains >256 disjoint intervals through real Host batches and retries ambiguous first batch exactly', async t => {
  const f = await deliveryFixture(t);
  const client = f.browser();
  await client.controller.flush();
  const count = 777;
  for (let index = 0; index < count; index++) {
    client.advance(1_000);
    client.controller.sample(true); // Genuine clock-generated 1s active interval.
    client.controller.sample(false, true); // Explicit inactive boundary.
    client.advance(1_000);
    client.controller.sample(true); // Resume; preceding inactive gap is excluded.
  }
  assert.equal(client.controller.getSnapshot().pendingMs, count * 1_000);
  assert.equal(client.controller.getSnapshot().durable, true);
  f.setFailAfterCommit(true);
  assert.equal(await client.controller.flush(), false);
  assert.deepEqual(f.committed(), { count: 256, total: 256_000 });
  assert.equal(client.controller.getSnapshot().pendingMs, count * 1_000);
  assert.equal(await client.controller.flush(), true);
  assert.equal(client.controller.getSnapshot().pendingMs, 0);
  assert.deepEqual(f.committed(), { count, total: count * 1_000 });
  assert.equal((await f.summary()).userMs, count * 1_000);
  const batches = f.calls.filter(body => body.op === 'activity');
  assert.deepEqual(batches.map(body => body.intervals.length), [256, 256, 256, 256, 9]);
  assert.deepEqual(batches[0], batches[1]);
  for (const body of batches) {
    assert.deepEqual(Object.keys(body).sort(), ['intervals', 'op']);
    assert.ok(body.intervals.length <= 256);
    for (const interval of body.intervals) {
      assert.deepEqual(Object.keys(interval).sort(), ['end', 'start']);
      assert.equal(interval.end - interval.start, 1_000);
    }
  }
  assert.deepEqual(f.reports, []);
});
