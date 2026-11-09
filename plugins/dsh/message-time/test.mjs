import { test } from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import { readFile } from 'node:fs/promises';
// The application ships Schemastery inside ASAR, unavailable to standalone Node.
// Capture the constructor calls only; this is NOT native validation/projection.
const schemaHook = registerHooks({ resolve(specifier, context, nextResolve) {
  if (specifier === '@deepseek-ai/schemastery') return {
    url: new URL('./schema-fixture.mjs', import.meta.url).href, shortCircuit: true,
  };
  return nextResolve(specifier, context);
} });
const { apply, formatStamp, Config } = await import('./index.js');
schemaHook.deregister();

function fixture(seed = [], config = {}) {
  const listeners = new Map();
  const observedStates = [];
  let cleanup;
  const ctx = { on: (name, fn) => listeners.set(name, fn),
    logger: () => ({ warn: (...args) => { throw new Error(args.join(' ')); } }),
    effect: fn => { cleanup = fn(); } };
  const session = { events: [...seed], id: 'test',
    snapshotEvents(from) { return this.events.slice(from); },
    append(type, message, options) {
      return emit(type, message, options);
    } };
  function emit(type, data, options = {}, time = Date.now()) {
    const event = { type, data, seq: session.events.length, time, ...options };
    session.events.push(event);
    listeners.get('session/event')?.(session, event);
    return event;
  }
  // Observe retention without shipping a production debug API. Tests run serially;
  // the temporary constructor interception covers apply() only, never an await.
  const NativeWeakMap = globalThis.WeakMap;
  globalThis.WeakMap = class extends NativeWeakMap {
    set(key, value) { observedStates.push(value); return super.set(key, value); }
  };
  try { apply(ctx, { timeZone: 'Europe/Moscow', ...config }); }
  finally { globalThis.WeakMap = NativeWeakMap; }
  async function propose(turn, messages = [], kind = 'enter') {
    return listeners.get('agent/pre-step')(
      { agent: { session }, turn, step: 1 }, async () => ({ kind, messages, startsRequestSeries: true }));
  }
  async function step(turn, messages = [], kind = 'enter') {
    const decision = await propose(turn, messages, kind);
    if (decision.kind === 'enter') for (const m of decision.messages) session.append('user/message', m, { surfaceOp: 'append' });
    return decision;
  }
  function splice(target, start, removedCount, inserted = [], outcome, time) {
    return emit('agent/inbox/spliced', { target, start, inserted,
      ...(removedCount ? { removedCount } : {}), ...(outcome ? { outcome } : {}) }, {}, time);
  }
  return { ctx, listeners, session, emit, splice, propose, step,
    state: () => observedStates.at(-1), dispose: () => cleanup?.() };
}
const user = (id, zone = 'Europe/Moscow') => ({ id, role: 'user', content: [{ type: 'text', text: 'hello' }], source: { kind: 'user', clientTimeZone: zone } });
const phases = decision => decision.messages.filter(m => m.source.kind === 'message-time').map(m => m.source.phase);
const tick = () => new Promise(resolve => queueMicrotask(resolve));

test('compact exact format, UTC, DST and invalid input', () => {
  const instant = Date.parse('2026-11-03T08:37:10Z');
  assert.equal(formatStamp(instant, 'Europe/Moscow'), '[2026-11-03 11:37:10 +03:00]');
  assert.equal(formatStamp(instant, 'UTC'), '[2026-11-03 08:37:10 +00:00]');
  assert.equal(formatStamp(Date.parse('2026-07-03T08:00:00Z'), 'America/New_York'), '[2026-07-03 04:00:00 -04:00]');
  assert.equal(formatStamp(NaN, 'UTC'), undefined);
  assert.equal(formatStamp('bad', 'UTC'), undefined);
});
test('user acceptance time and one start per full turn, not per step', async () => {
  const f = fixture(); const m = user('u'); const accepted = Date.parse('2026-11-03T08:00:00Z');
  f.splice('next-turn', 0, 0, [m], undefined, accepted);
  f.emit('turn/start', { turn: 1 });
  f.splice('next-turn', 0, 1); // native claim: no canceled outcome
  const d = await f.step(1, [m]);
  assert.deepEqual(phases(d), ['user', 'turn-start']);
  assert.equal(d.messages[1].content[0].text, '[2026-11-03 11:00:00 +03:00]');
  assert.equal(d.startsRequestSeries, true);
  assert.deepEqual(phases(await f.step(1)), []);
  assert.deepEqual(phases(await f.step(2)), ['turn-start']);
});
test('every human input including mid-turn input, no synthetic-input stamp', async () => {
  const f = fixture();
  await f.step(1);
  const d = await f.step(1, [user('a'), user('b'), { id: 's', role: 'user', source: { kind: 'system' }, content: [] }]);
  assert.deepEqual(phases(d), ['user', 'user']);
});
test('new built-in verbose clocks are replaced, unrelated context preserved', async () => {
  const f = fixture();
  const d = await f.step(1, [
    { id: 'clock', source: { kind: 'time-context' }, content: [] },
    { id: 'other', source: { kind: 'other' }, content: [] },
  ]);
  assert.equal(d.messages.some(m => m.id === 'clock'), false);
  assert.equal(d.messages[0].id, 'other');
  assert.deepEqual(phases(d), ['turn-start']);
});
test('rejected step creates no clocks', async () => {
  const f = fixture();
  assert.equal((await f.step(1, [user('u')], 'reject')).kind, 'reject');
  assert.equal(f.session.events.length, 0);
  assert.deepEqual(phases(await f.step(1)), ['turn-start']);
});
test('no assistant/tool/step stamps; completed turn gets exactly one end', async () => {
  const f = fixture(); await f.step(1, [user('u')]);
  const n = f.session.events.length;
  f.emit('assistant/message', { message: { role: 'assistant' } }, { surfaceOp: 'append' });
  f.emit('tool/result', {}); f.emit('step/end', {});
  await tick(); assert.equal(f.session.events.length, n + 3);
  f.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }, {}, Date.parse('2026-11-03T08:45:00Z'));
  await tick();
  const last = f.session.events.at(-1).data;
  assert.equal(last.source.phase, 'turn-end');
  assert.equal(last.content[0].text, '[2026-11-03 11:45:00 +03:00]');
  f.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }); await tick();
  assert.equal(f.session.events.filter(e => e.data?.source?.phase === 'turn-end').length, 1);
});
test('aborted and failed turns are not described as completed', async () => {
  const f = fixture();
  for (const kind of ['aborted', 'error', 'interrupted', 'blocked']) f.emit('turn/end', { turn: 1, reason: { kind } });
  await tick(); assert.equal(f.session.events.length, 4);
});
test('reload/fork derives zone and turn markers without changing settled history', async () => {
  const f = fixture(); await f.step(7, [user('u', 'America/New_York')]);
  const before = JSON.stringify(f.session.events);
  const restored = fixture(f.session.events);
  assert.deepEqual(phases(await restored.step(7)), []);
  restored.emit('turn/end', { turn: 7, reason: { kind: 'completed' } }, {}, Date.parse('2026-11-03T08:45:00Z'));
  await tick();
  assert.equal(restored.session.events.at(-1).data.content[0].text, '[2026-11-03 03:45:00 -05:00]');
  assert.equal(JSON.stringify(f.session.events), before);
});
test('zones remain session-local even under one plugin instance', async () => {
  const f = fixture(); await f.step(1, [user('u', 'America/New_York')]);
  const other = { id: 'other', events: [], snapshotEvents(from) { return this.events.slice(from); } };
  const d = await f.listeners.get('agent/pre-step')({ agent: { session: other }, turn: 1 }, async () => ({ kind: 'enter', messages: [user('v')] }));
  assert.equal(d.messages.at(-1).source.timeZone, 'Europe/Moscow');
  f.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }, {}, Date.parse('2026-11-03T08:45:00Z')); await tick();
  assert.equal(f.session.events.at(-1).data.content[0].text, '[2026-11-03 03:45:00 -05:00]');
});
test('unload cancels queued writes', async () => {
  const f = fixture(); f.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }); f.dispose(); await tick();
  assert.equal(f.session.events.length, 1);
});

test('unload leaves an in-flight pre-step decision and subsequent events untouched', async () => {
  const f = fixture();
  let resume;
  const decision = { kind: 'enter', messages: [user('u')], startsRequestSeries: true };
  const pending = f.listeners.get('agent/pre-step')(
    { agent: { session: f.session }, turn: 1 }, () => new Promise(resolve => { resume = resolve; }));
  f.dispose(); resume(decision);
  assert.equal(await pending, decision);
  f.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }); await tick();
  assert.equal(f.session.events.length, 1);
  assert.equal(f.state(), undefined);
});

const receipt = (decision, id) => decision.messages.find(m => m.source?.messageId === id)?.content[0].text;
const oldTime = Date.parse('2020-01-01T00:00:00Z');

test('cancellation-only idle traffic stays bounded without another model step', async () => {
  const f = fixture([], { includeTurnStart: false });
  for (let i = 0; i < 1000; i++) {
    f.splice('next-turn', 0, 0, [user(`cancel-${i}`)], undefined, oldTime + i);
    await f.propose(1); // receipt observed before cancellation; no following step required
    f.splice('next-turn', 0, 1, [], 'canceled');
  }
  assert.equal(f.state().received.size, 0);
  assert.deepEqual(f.state().pending, { 'next-turn': [], 'next-step': [] });
  assert.equal(f.state().claimed.size, 0);
});
test('cancel and replace prune removed identities; a reused id gets a new receipt', async () => {
  const f = fixture(); const a = user('a'), b = user('b'), c = user('c');
  f.splice('next-turn', 0, 0, [a, b, c], undefined, oldTime);
  await f.propose(1);
  f.splice('next-turn', 1, 1, [user('replacement')], 'canceled', oldTime + 1000);
  f.splice('next-turn', 0, 1, [], 'canceled');
  f.splice('next-turn', 0, 1, [user('replacement')], 'canceled', oldTime + 2000);
  const d = await f.propose(1, [user('replacement'), c]);
  assert.deepEqual([...f.state().received.keys()].sort(), ['c', 'replacement']);
  assert.equal(receipt(d, 'replacement'), formatStamp(oldTime + 2000, 'Europe/Moscow'));
  assert.equal(receipt(d, 'c'), formatStamp(oldTime, 'Europe/Moscow'));
});
test('claimed next-step and next-turn receipts survive before admission and pending cancellation', async () => {
  const f = fixture(); const a = user('a'), b = user('b'), later = user('later');
  f.splice('next-turn', 0, 0, [a, later], undefined, oldTime);
  f.splice('next-step', 0, 0, [b], undefined, oldTime + 1000);
  f.emit('turn/start', { turn: 1 });
  f.splice('next-step', 0, 1);
  f.splice('next-turn', 0, 1);
  f.splice('next-turn', 0, 1, [], 'canceled');
  const d = await f.propose(1, [b, a]);
  assert.equal(receipt(d, 'a'), formatStamp(oldTime, 'Europe/Moscow'));
  assert.equal(receipt(d, 'b'), formatStamp(oldTime + 1000, 'Europe/Moscow'));
  assert.equal(f.state().received.has('later'), false);
  assert.equal(f.state().received.size, 2);
  await f.step(1, [b, a]);
  assert.equal(f.state().received.size, 0);
  assert.equal(f.state().claimed.size, 0);
});
test('terminal turns clear uncommitted claims but keep genuinely pending receipts', async () => {
  for (const kind of ['aborted', 'blocked', 'error', 'interrupted', 'completed']) {
    const f = fixture([], { includeAssistant: false });
    f.splice('next-turn', 0, 0, [user('claim'), user('pending')], undefined, oldTime);
    f.emit('turn/start', { turn: 1 }); f.splice('next-turn', 0, 1);
    // Also covers abort during request assembly, after pre-step accepted but before commit.
    await f.propose(1, [user('claim')], kind === 'blocked' ? 'reject' : 'enter');
    f.emit('turn/end', { turn: 1, reason: { kind } });
    const d = await f.propose(2, [user('pending')]);
    assert.deepEqual([...f.state().received.keys()], ['pending'], kind);
    assert.equal(f.state().claimed.size, 0, kind);
    assert.equal(receipt(d, 'pending'), formatStamp(oldTime, 'Europe/Moscow'), kind);
  }
});
test('replay and fork retain in-flight claims, exclude cancellations, and never mutate history', async () => {
  const f = fixture();
  f.splice('next-turn', 0, 0, [user('canceled'), user('claim'), user('pending')], undefined, oldTime);
  f.splice('next-turn', 0, 1, [], 'canceled');
  f.emit('turn/start', { turn: 3 }); f.splice('next-turn', 0, 1);
  const before = JSON.stringify(f.session.events);
  const restored = fixture(f.session.events);
  assert.equal(receipt(await restored.propose(3, [user('claim')]), 'claim'), formatStamp(oldTime, 'Europe/Moscow'));
  assert.deepEqual([...restored.state().received.keys()], ['claim', 'pending']);
  restored.emit('turn/end', { turn: 3, reason: { kind: 'interrupted' } });
  const forked = fixture(restored.session.events);
  await forked.propose(4);
  assert.deepEqual([...forked.state().received.keys()], ['pending']);
  assert.equal(JSON.stringify(f.session.events), before);
});
test('retention scales with live pending/claimed work, not settled session history', async () => {
  const f = fixture([], { includeAssistant: false });
  for (let turn = 1; turn <= 100; turn++) {
    f.splice('next-turn', 0, 0, [user(`u-${turn}`)], undefined, oldTime);
    f.emit('turn/start', { turn }); f.splice('next-turn', 0, 1);
    await f.step(turn, [user(`u-${turn}`)]);
    f.emit('turn/end', { turn, reason: { kind: 'completed' } });
  }
  f.splice('next-step', 0, 0, [user('pending')], undefined, oldTime);
  await f.propose(101);
  assert.equal(f.state().received.size, 1);
  assert.equal(f.state().claimed.size, 0);
  assert.deepEqual(f.state().pending, { 'next-turn': [], 'next-step': ['pending'] });
});
test('synthetic pending identities preserve splice positions without retaining receipt times', async () => {
  const f = fixture(); const synthetic = { id: 'system', source: { kind: 'system' }, content: [] };
  f.splice('next-step', 0, 0, [synthetic, user('u')], undefined, oldTime);
  f.splice('next-step', 0, 1, [], 'canceled');
  f.emit('turn/start', { turn: 1 }); f.splice('next-step', 0, 1);
  assert.equal(receipt(await f.propose(1, [user('u')]), 'u'), formatStamp(oldTime, 'Europe/Moscow'));
  assert.deepEqual([...f.state().received.keys()], ['u']);
});
test('Config uses the native schema constructor for five optional fields', () => {
  assert.ok(Config, 'named Config export');
  assert.equal(Config.type, 'object');
  assert.deepEqual(Object.keys(Config.dict), ['enabled', 'includeUser', 'includeAssistant', 'includeTurnStart', 'timeZone']);
  for (const key of ['enabled', 'includeUser', 'includeAssistant', 'includeTurnStart']) {
    assert.equal(Config.dict[key].type, 'boolean');
    assert.equal(Config.dict[key].meta.default, true);
    assert.ok(Config.dict[key].meta.description);
  }
  assert.equal(Config.dict.timeZone.type, 'string');
  assert.equal(Config.dict.timeZone.meta.default, undefined);
  assert.match(Config.dict.timeZone.meta.description, /host/i);
  for (const locale of ['en', 'ru']) {
    assert.deepEqual(Object.keys(Config.localeCalls[locale]), Object.keys(Config.dict));
    for (const description of Object.values(Config.localeCalls[locale])) assert.ok(description.length > 20);
  }
});
test('package pins inspected DSH and declares the real schema dependency; fixtures are not shipped', async () => {
  const pkg = JSON.parse(await readFile(new URL('./package.json', import.meta.url), 'utf8'));
  assert.equal(pkg.version, '1.2.1');
  assert.equal(pkg.engines?.dsh, '0.2.2-rc.1');
  assert.equal(pkg.dependencies?.['@deepseek-ai/schemastery'], '~3.19.0');
  assert.equal(pkg.files.includes('schema-fixture.mjs'), false);
  assert.equal(pkg.files.includes('test.mjs'), false);
});
test('all config switches retain their existing runtime meaning', async () => {
  const disabled = fixture([], { enabled: false });
  assert.equal(disabled.listeners.size, 0);
  const userOff = fixture([], { includeUser: false });
  assert.deepEqual(phases(await userOff.step(1, [user('u')])), ['turn-start']);
  const startOff = fixture([], { includeTurnStart: false });
  assert.deepEqual(phases(await startOff.step(1, [user('u')])), ['user']);
  const endOff = fixture([], { includeAssistant: false });
  endOff.emit('turn/end', { turn: 1, reason: { kind: 'completed' } }); await tick();
  assert.equal(endOff.session.events.length, 1);
});
test('missing or invalid configured zones fall back to host; valid browser zone wins', async () => {
  for (const timeZone of [undefined, '', 'Invalid/Zone']) {
    const f = fixture([], { timeZone });
    f.splice('next-turn', 0, 0, [user('u', 'invalid')], undefined, oldTime);
    assert.equal(receipt(await f.propose(1, [user('u', 'invalid')]), 'u'), formatStamp(oldTime));
  }
  const f = fixture([], { timeZone: 'Europe/Moscow' });
  f.splice('next-turn', 0, 0, [user('u', 'UTC')], undefined, oldTime);
  assert.equal(receipt(await f.propose(1, [user('u', 'UTC')]), 'u'), formatStamp(oldTime, 'UTC'));
});
