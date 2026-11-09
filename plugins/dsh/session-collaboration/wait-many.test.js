import test from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { createWaitMany } from './wait-many.js';

const value = (reason = 'idle', records = []) => ({ reason,
  state: { cursor: 10, active: true, running: reason === 'timeout', queue: [],
    pendingInput: reason === 'input-required' ? ['question'] : [] },
  output: { records, truncated: false } });
const record = (seq, text, extra = []) => ({ type: 'event', event: {
  seq, type: 'assistant/message', surfaceOp: 'append', data: {
    message: { id: `message-${seq}`, content: [{ type: 'text', text }, ...extra] } } } });
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
async function turns() { for (let i = 0; i < 8; i++) await Promise.resolve(); }
function fixture(wait) {
  const calls = [], forbidden = [];
  const controller = { wait: (request, signal) => { calls.push({ request, signal }); return wait(request, signal); } };
  for (const method of ['cancel', 'resolveAgent', 'create', 'prompt'])
    controller[method] = () => { forbidden.push(method); throw new Error('Forbidden target mutation'); };
  return { api: createWaitMany({ sessionController: controller }), calls, forbidden };
}

test('defaults, distinct targets, native request bounds, and independent all-mode statuses', async () => {
  const f = fixture(async ({ sessionId }) => value(sessionId === 'a' ? 'idle' : 'input-required'));
  const result = await f.api.waitMany({ targets: [{ sessionId: 'a' }, { sessionId: 'b', afterSeq: 9 }] });
  assert.equal(result.scope, 'session-window');
  assert.equal(result.mode, 'all');
  assert.equal(result.reason, 'all');
  assert.deepEqual(result.results.map(row => row.reason), ['idle', 'input-required']);
  assert.deepEqual(f.calls.map(call => call.request.afterSeq), [-1, 9]);
  assert(f.calls.every(call => call.request.timeoutMs > 28000 && call.request.timeoutMs <= 29000));
  assert(f.calls.every(call => call.request.maxMessages === 10));
  assert.match(result.note, /not guaranteed replies or task completion/);
  assert.match(result.note, /Only observation stops; targets are unchanged/);
  assert.deepEqual(f.forbidden, []);
  await f.api.dispose();
});

test('invalid input never reaches the native service', async () => {
  const f = fixture(async () => value());
  const valid = { targets: [{ sessionId: 'a' }] };
  const invalid = [ {}, { targets: [] }, { targets: Array.from({ length: 9 }, (_, i) => ({ sessionId: `s${i}` })) },
    { targets: [{ sessionId: 'a' }, { sessionId: 'a' }] }, { targets: [null] },
    { targets: [{ sessionId: '../bad' }] }, { targets: [{ sessionId: 'a', afterSeq: -2 }] },
    { targets: [{ sessionId: 'a', afterSeq: 1.5 }] }, { ...valid, mode: 'race' },
    ...[0, 120001, 1.5, NaN].map(timeoutMs => ({ ...valid, timeoutMs })) ];
  for (const args of invalid) await assert.rejects(f.api.waitMany(args), { code: 'invalid-input' });
  assert.equal(f.calls.length, 0);
  await f.api.dispose();
});

test('any idle or input-required cancels only pending observer waits', async () => {
  for (const reason of ['idle', 'input-required']) {
    const winner = deferred();
    const f = fixture(({ sessionId }) => sessionId === 'winner' ? winner.promise : new Promise(() => {}));
    const task = f.api.waitMany({ targets: [{ sessionId: 'slow' }, { sessionId: 'winner' }], mode: 'any' });
    await turns();
    winner.resolve(value(reason));
    const result = await task;
    assert.equal(result.reason, 'any');
    assert.deepEqual(result.results.map(row => row.reason), ['stopped', reason]);
    assert(f.calls.every(call => call.signal.aborted));
    assert.deepEqual(f.forbidden, []);
    await f.api.dispose();
  }
});

test('target errors are bounded per-target observations; missing sessions never activate', async () => {
  const f = fixture(async ({ sessionId }) => {
    if (sessionId === 'missing') throw Object.assign(new Error('private unbounded diagnostic'), { code: 'session/not-found' });
    if (sessionId === 'bad') throw new Error('private native stack');
    return value();
  });
  const result = await f.api.waitMany({ targets: ['missing', 'good', 'bad'].map(sessionId => ({ sessionId })) });
  assert.equal(result.reason, 'all');
  assert.deepEqual(result.results.map(row => row.reason), ['error', 'idle', 'error']);
  assert.equal(result.results[0].error.code, 'session/not-found');
  assert.equal(result.results[2].error.code, 'wait-failed');
  assert.doesNotMatch(JSON.stringify(result), /private/);
  assert.deepEqual(f.forbidden, []);
  await f.api.dispose();
});

test('any-mode observation error stops siblings but does not claim success', async () => {
  const failure = deferred();
  const f = fixture(({ sessionId }) => sessionId === 'broken' ? failure.promise : new Promise(() => {}));
  const task = f.api.waitMany({ targets: [{ sessionId: 'broken' }, { sessionId: 'slow' }], mode: 'any' });
  await turns();
  failure.reject(Object.assign(new Error('no'), { code: 'session/not-found' }));
  const result = await task;
  assert.equal(result.reason, 'any');
  assert.deepEqual(result.results.map(row => row.reason), ['error', 'stopped']);
  assert.match(result.note, /not guaranteed replies or task completion/);
  await f.api.dispose();
});

test('native returned timeout and native wait-timeout errors cannot win any-mode early', async () => {
  for (const nativeError of [false, true]) {
    const winner = deferred();
    const f = fixture(async ({ sessionId }) => {
      if (sessionId === 'winner') return winner.promise;
      if (nativeError) throw Object.assign(new Error('first sample'), { code: 'session/wait-timeout' });
      return value('timeout');
    });
    let settled = false;
    const task = f.api.waitMany({ targets: [{ sessionId: 'window' }, { sessionId: 'winner' }], mode: 'any', timeoutMs: 500 })
      .then(result => { settled = true; return result; });
    await turns();
    assert.equal(settled, false);
    assert.equal(f.calls[1].signal.aborted, false);
    winner.resolve(value());
    const result = await task;
    assert.equal(result.reason, 'any');
    assert.deepEqual(result.results.map(row => row.reason), ['stopped', 'idle']);
    await f.api.dispose();
  }
});

test('a timeout window retries with decreasing remaining deadline and unchanged afterSeq', async () => {
  const f = fixture(async () => f.calls.length === 1 ? value('timeout') : value());
  const result = await f.api.waitMany({ targets: [{ sessionId: 'a', afterSeq: 5 }], mode: 'any', timeoutMs: 300 });
  assert.equal(result.reason, 'any');
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1].request.afterSeq, 5);
  assert(f.calls[1].request.timeoutMs < f.calls[0].request.timeoutMs);
  await f.api.dispose();
});

test('native wait-timeout can recover to idle without retaining a stale error', async () => {
  const f = fixture(async () => {
    if (f.calls.length === 1) throw Object.assign(new Error('sample'), { code: 'session/wait-timeout' });
    return value();
  });
  const result = await f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 300 });
  assert.equal(result.reason, 'all');
  assert.equal(result.results[0].reason, 'idle');
  assert.equal(result.results[0].error, undefined);
  assert.equal(f.calls.length, 2);
  await f.api.dispose();
});

test('normal delayed native timeout retains a snapshot before the hard cutoff', async () => {
  const f = fixture(async (request, signal) => {
    await delay(request.timeoutMs, undefined, { signal });
    return value('timeout', [record(8, 'last observed snapshot')]);
  });
  const result = await f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 150 });
  assert.equal(result.reason, 'timeout');
  assert.equal(result.results[0].reason, 'timeout');
  assert.equal(result.results[0].state.cursor, 10);
  assert.equal(result.results[0].output.records[0].text, 'last observed snapshot');
  assert(f.calls[0].request.timeoutMs <= 135);
  assert.match(result.note, /Timeout may retain an earlier sample/);
  await f.api.dispose();
});

test('any-mode keeps observing after a delayed timeout sample and accepts another terminal', async () => {
  const sampleReturned = deferred();
  const f = fixture(async (request, signal) => {
    if (request.sessionId === 'winner') {
      await sampleReturned.promise;
      await delay(2, undefined, { signal });
      return value('input-required');
    }
    await delay(request.timeoutMs, undefined, { signal });
    sampleReturned.resolve();
    return value('timeout', [record(8, 'partial before other target')]);
  });
  const result = await f.api.waitMany({ targets: [{ sessionId: 'window' }, { sessionId: 'winner' }], mode: 'any', timeoutMs: 200 });
  assert.equal(result.reason, 'any');
  assert.deepEqual(result.results.map(row => row.reason), ['stopped', 'input-required']);
  assert.equal(result.results[0].output.records[0].text, 'partial before other target');
  assert(f.calls.every(call => call.signal.aborted));
  await f.api.dispose();
});

test('the minimum timeout is accepted and remains a deadline', async () => {
  const f = fixture(() => new Promise(() => {}));
  const result = await f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 1 });
  assert.equal(result.reason, 'timeout');
  assert.equal(result.results[0].reason, 'timeout');
  assert(f.calls.every(call => call.request.timeoutMs === 1));
  await f.api.dispose();
});

test('all-mode has one deadline even if eight observers ignore cancellation', async () => {
  const f = fixture(() => new Promise(() => {}));
  const started = performance.now();
  const result = await f.api.waitMany({ targets: Array.from({ length: 8 }, (_, i) => ({ sessionId: `s${i}` })), timeoutMs: 30 });
  assert.equal(result.reason, 'timeout');
  assert(result.results.every(row => row.reason === 'timeout'));
  assert.equal(f.calls.length, 8);
  assert(f.calls.every(call => call.signal.aborted));
  assert(performance.now() - started < 200, 'must not wait for eight serial deadlines');
  assert.deepEqual(f.forbidden, []);
  await f.api.dispose();
});

test('repeated immediate native timeout is bounded and not successful completion', async () => {
  for (const nativeError of [false, true]) {
    const f = fixture(async () => {
      if (nativeError) throw Object.assign(new Error('sample'), { code: 'session/wait-timeout' });
      return value('timeout', [record(2, 'partial')]);
    });
    const result = await f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 35, mode: 'any' });
    assert.equal(result.reason, 'timeout');
    assert.equal(result.results[0].reason, 'timeout');
    assert(f.calls.length >= 1 && f.calls.length <= 5);
    if (nativeError) assert.equal(result.results[0].error.code, 'session/wait-timeout');
    else assert.equal(result.results[0].output.records[0].text, 'partial');
    await f.api.dispose();
  }
});

test('completed rows remain independent when the remaining target reaches deadline', async () => {
  const f = fixture(async ({ sessionId }) => sessionId === 'done' ? value() : new Promise(() => {}));
  const result = await f.api.waitMany({ targets: [{ sessionId: 'done' }, { sessionId: 'slow' }], timeoutMs: 10 });
  assert.equal(result.reason, 'timeout');
  assert.deepEqual(result.results.map(row => row.reason), ['idle', 'timeout']);
  await f.api.dispose();
});

test('external tool abort rejects with exact reason; pre-abort never starts a wait', async () => {
  const external = new AbortController(), error = new Error('caller stopped');
  const native = deferred();
  const f = fixture(() => native.promise);
  const task = f.api.waitMany({ targets: [{ sessionId: 'a' }] }, { signal: external.signal });
  await turns();
  external.abort(error);
  await assert.rejects(task, thrown => thrown === error);
  assert(f.calls.every(call => call.signal.aborted));
  // Late service rejection is consumed, including for a non-cooperative wait.
  native.reject(new Error('late failure'));
  await turns();
  await assert.rejects(f.api.waitMany({ targets: [{ sessionId: 'b' }] }, { signal: external.signal }), thrown => thrown === error);
  assert.equal(f.calls.length, 1);
  await f.api.dispose();
});

test('dispose aborts concurrent observers and disables new observations', async () => {
  const f = fixture(() => new Promise(() => {}));
  const tasks = [f.api.waitMany({ targets: [{ sessionId: 'a' }] }), f.api.waitMany({ targets: [{ sessionId: 'b' }] })];
  const results = Promise.allSettled(tasks);
  await turns();
  await f.api.dispose();
  assert((await results).every(result => result.status === 'rejected' && /unloaded/.test(result.reason.message)));
  assert(f.calls.every(call => call.signal.aborted));
  await assert.rejects(f.api.waitMany({ targets: [{ sessionId: 'c' }] }), /unloaded/);
  assert.equal(f.calls.length, 2);
});

test('aggregate output is bounded newest-first assistant text without private content', async () => {
  const f = fixture(async () => value('idle', [record(1, 'excluded old cut'), record(3, 'x'.repeat(50000)),
    record(9, 'latest', [{ type: 'thinking', text: 'PRIVATE' }, { type: 'tool-call', input: 'PRIVATE' }]),
    { event: { ...record(10, 'PRIVATE').event, surfaceOp: 'replace' } },
    { event: { seq: 11, type: 'user/message', surfaceOp: 'append', data: { content: [{ type: 'text', text: 'PRIVATE' }] } } }]));
  const result = await f.api.waitMany({ targets: Array.from({ length: 8 }, (_, i) => ({ sessionId: `s${i}`, afterSeq: 1 })) });
  const total = result.results.flatMap(row => row.output.records).reduce((n, item) => n + item.text.length, 0);
  assert.equal(total, 32000);
  assert(result.truncated);
  for (const row of result.results) {
    assert.deepEqual(row.output.records.map(item => item.seq), [9, 3]);
    assert.equal(row.output.records[0].text, 'latest');
    assert.equal(row.output.truncated, true);
  }
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE|excluded old cut/);
  await f.api.dispose();
});

test('early completion clears the long deadline timer', async t => {
  const handles = new Set();
  const set = globalThis.setTimeout, clear = globalThis.clearTimeout;
  t.mock.method(globalThis, 'setTimeout', (...args) => { const handle = set(...args); handles.add(handle); return handle; });
  t.mock.method(globalThis, 'clearTimeout', handle => { handles.delete(handle); return clear(handle); });
  const f = fixture(async () => value());
  await f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 120000 });
  assert.equal(handles.size, 0);
  await f.api.dispose();
});

test('cancelling a retry backoff leaves no observer retry running', async () => {
  const external = new AbortController();
  const f = fixture(async () => value('timeout'));
  const task = f.api.waitMany({ targets: [{ sessionId: 'a' }], timeoutMs: 120000 }, { signal: external.signal });
  await turns();
  external.abort(new Error('stop backoff'));
  await assert.rejects(task, /stop backoff/);
  const count = f.calls.length;
  await delay(20);
  assert.equal(f.calls.length, count);
  await f.api.dispose();
});
