import { test } from 'node:test';
import assert from 'node:assert/strict';
import { apply, formatStamp } from './index.js';

function fixture(seed = []) {
  const listeners = new Map();
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
  apply(ctx, { timeZone: 'Europe/Moscow' });
  async function step(turn, messages = [], kind = 'enter') {
    const decision = await listeners.get('agent/pre-step')(
      { agent: { session }, turn, step: 1 }, async () => ({ kind, messages, startsRequestSeries: true }));
    if (decision.kind === 'enter') for (const m of decision.messages) session.append('user/message', m, { surfaceOp: 'append' });
    return decision;
  }
  return { ctx, listeners, session, emit, step, dispose: () => cleanup() };
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
  f.emit('agent/inbox/spliced', { inserted: [m] }, {}, accepted);
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
