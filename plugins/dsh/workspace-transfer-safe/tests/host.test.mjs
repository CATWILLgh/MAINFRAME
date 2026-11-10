import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { apply, moveSession, TransferError, validateSource } from '../index.js';

// No native profile or user sessions are accessed. Filesystem fixtures contain
// only empty directories and are retained; these tests never erase anything.
const root = await realpath(await mkdtemp(join(tmpdir(), 'dsh-transfer-unit-')));
let counter = 0;
const clone = value => structuredClone(value);
const event = (type, data = {}, seq = 0) => ({ type, data, seq, time: 1000 });
const baseHeader = { version: 4, id: 'session-source', createdAt: 1000, isSeeded: false };
const simpleEvents = () => [event('session/title', { title: 'Test', messageSeqs: [], source: { kind: 'user' } })];
const rejectsCode = (promise, code) => assert.rejects(promise, error => error instanceof TransferError && error.code === code);

async function fixture(options = {}) {
  const dir = join(root, String(++counter));
  await mkdir(dir);
  await mkdir(join(dir, 'source'));
  await mkdir(join(dir, 'target'));
  const sourcePath = await realpath(join(dir, 'source'));
  const targetPath = await realpath(join(dir, 'target'));
  const header = { ...baseHeader, cwd: sourcePath, agentPreset: 'fixture-preset', ...options.header };
  const events = options.events ?? simpleEvents();
  const records = new Map([[header.id, { header: clone(header), events: clone(events), inheritedEventCount: 0 }]]);
  const owned = new Set();
  const actions = [];
  const archived = [];
  const state = { ...options, liveAgent: false, liveSession: false };
  const target = {
    id: 'workspace-target', path: targetPath, sessionIds: [], title: 'Target',
    async attachSession(id) {
      actions.push(['attach', id]);
      if (state.attachError) throw Error('attach failed');
      this.sessionIds.push(id);
    },
  };
  function handle(id, access) {
    const record = records.get(id);
    let closed = false;
    return {
      header: clone(record.header), inheritedEventCount: record.inheritedEventCount,
      async read() {
        assert.ok(!closed);
        actions.push(['read', id]);
        if (id === header.id) await state.sourceRead?.();
        const readEvents = clone(record.events);
        if (id !== header.id && state.corruptReadback) readEvents.pop();
        return { eventState: 'detached', events: readEvents };
      },
      async append(batch) {
        assert.equal(access, 'write');
        assert.ok(!closed);
        actions.push(['append', id]);
        if (state.appendError) throw Error('append failed');
        assert.equal(batch[0]?.seq, record.events.length);
        record.events.push(...clone(batch));
      },
      async flush() {
        actions.push(['flush', id]);
        if (state.flushError) throw Error('flush failed');
      },
      async close() {
        if (closed) return;
        closed = true;
        actions.push(['close', id]);
        owned.delete(id);
        if (id === header.id && state.sourceCloseError) throw Error('source close failed');
        if (id !== header.id && state.destinationCloseError) throw Error('destination close failed');
      },
    };
  }
  const persistence = {
    async open(id, access) {
      actions.push(['open', id, access]);
      if (!records.has(id)) throw Object.assign(Error('missing'), { name: 'SessionPersistenceNotFoundError' });
      if (access === 'write' && owned.has(id)) throw Object.assign(Error('owned'), { name: 'SessionAlreadyOwnedError' });
      if (access === 'write') owned.add(id);
      await state.afterOpen?.(id, access);
      return handle(id, access);
    },
    async create(newHeader, opts = {}) {
      actions.push(['create', newHeader.id]);
      if (state.createError) throw Error('create failed');
      assert.ok(!records.has(newHeader.id));
      records.set(newHeader.id, { header: clone(newHeader), events: [], inheritedEventCount: opts.inheritedEventCount ?? 0 });
      owned.add(newHeader.id);
      return handle(newHeader.id, 'write');
    },
  };
  const ctx = {
    sessionPersistence: persistence,
    agents: { get: id => id === header.id && state.liveAgent ? {} : undefined },
    sessions: { get: id => id === header.id && state.liveSession ? {} : undefined },
    workspaceRegistry: {
      archivedSessionIds: archived,
      get: id => id === target.id ? target : undefined,
      list: () => [target],
      async archiveSession(id, opts) {
        actions.push(['archive', id, opts]);
        assert.equal(opts?.stopActivity, undefined, 'never stop source activity');
        if (state.archiveError) throw Error('archive failed');
        archived.push(id);
      },
    },
    permissionPresets: { catalog: () => ({ defaultOptions: state.presets ?? [{ value: 'fixture-safe' }] }) },
    async waterfall(name, payload) {
      assert.equal(name, 'workspace/session-activity');
      assert.deepEqual(payload, { sessionId: header.id });
      return state.activity ?? [];
    },
    sessionQuery: {
      async readSession(id) {
        actions.push(['replay', id]);
        if (state.replayError) throw Error('native replay failed');
        const record = records.get(id);
        return { session: clone(record.header), events: clone(record.events) };
      },
    },
    sessionProjectionCache: {
      coldSnapshot(newHeader, cut, seed) {
        actions.push(['projections', newHeader.id]);
        assert.equal(cut, events.length);
        const last = type => seed.findLast(e => e.type === type)?.data;
        return { asOfSeq: seed.length - 1, values: {
          workingDirectory: state.badCwdProjection ? sourcePath : last('working-directory/change').cwd,
          permissions: { currentValue: state.badPermissionProjection ? 'auto' : 'custom' },
        } };
      },
    },
    emit(name, payload) { actions.push(['emit', payload.sessionId]); if (state.emitError) throw Error('emit failed'); },
  };
  return { ctx, state, records, owned, actions, archived, target, header, events };
}

for (const [name, header, events, code] of [
  ['future format', { version: 5 }, simpleEvents(), 'unsupported-format'],
  ['seeded header', { isSeeded: true }, simpleEvents(), 'seeded-source'],
  ['parent lineage', { parentSession: 'parent' }, simpleEvents(), 'seeded-source'],
  ['subagent origin', { origin: 'subagent' }, simpleEvents(), 'seeded-source'],
  ['delegation depth', { delegationDepth: 1 }, simpleEvents(), 'seeded-source'],
  ['empty history', {}, [], 'blank-session'],
  ['sequence gap', {}, [event('session/title', {}, 1)], 'invalid-history'],
  ['invalid time', {}, [{ ...simpleEvents()[0], time: NaN }], 'invalid-history'],
  ['nested seed marker', {}, [event('session/end-seed', { inherited: true })], 'seeded-source'],
  ['open turn', {}, [event('turn/start')], 'open-turn'],
  ['open step', {}, [event('step/start')], 'open-turn'],
  ['pending inbox', {}, [event('agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [{ id: 'pending' }] })], 'pending-inbox'],
  ['invalid inbox target', {}, [event('agent/inbox/spliced', { target: 'bad', start: 0, inserted: [] })], 'invalid-inbox'],
  ['invalid inbox index', {}, [event('agent/inbox/spliced', { target: 'next-turn', start: 1, inserted: [] })], 'invalid-inbox'],
  ['invalid inbox removal', {}, [event('agent/inbox/spliced', { target: 'next-turn', start: 0, removedCount: -1, inserted: [] })], 'invalid-inbox'],
  ['missing inbox identity', {}, [event('agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [{}] })], 'invalid-inbox'],
  ['duplicate inbox identity', {}, [event('agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [{id:'duplicate'}, {id:'duplicate'}] })], 'invalid-inbox'],
  ['duplicate identity across queues', {}, [
    event('agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [{id:'duplicate'}] }),
    event('agent/inbox/spliced', { target: 'next-step', start: 0, inserted: [{id:'duplicate'}] }, 1),
  ], 'invalid-inbox'],
]) {
  test(`validateSource refuses ${name}`, () => {
    assert.throws(() => validateSource({ ...baseHeader, ...header }, events), e => e instanceof TransferError && e.code === code);
  });
}

test('validateSource allows consumed inbox and completed turn history', () => {
  const entries = [
    ['agent/inbox/spliced', { target: 'next-turn', start: 0, inserted: [{ id: 'done' }] }],
    ['agent/inbox/spliced', { target: 'next-turn', start: 0, removedCount: 1, inserted: [] }],
    ['turn/start', {}], ['step/start', {}], ['step/end', {}], ['turn/end', {}],
  ].map(([type, data], seq) => event(type, data, seq));
  assert.doesNotThrow(() => validateSource(baseHeader, entries));
});

test('cold transfer preserves prefix, resets cwd/permissions, archives last and closes both handles', async () => {
  const f = await fixture();
  const original = clone(f.records.get(f.header.id));
  const result = await moveSession(f.ctx, f.header.id, f.target.id);
  assert.deepEqual(result, { ok: true, sessionId: result.sessionId, workspaceId: f.target.id, copied: true, sourceArchived: true });
  assert.notEqual(result.sessionId, f.header.id);
  const copy = f.records.get(result.sessionId);
  assert.equal(copy.header.cwd, f.target.path);
  assert.equal(copy.header.isSeeded, true);
  assert.equal(copy.header.agentPreset, 'fixture-preset');
  assert.equal(copy.header.parentSession, undefined);
  assert.equal(copy.inheritedEventCount, f.events.length);
  assert.deepEqual(copy.events.slice(0, f.events.length), f.events);
  assert.deepEqual(copy.events.slice(f.events.length).map(e => [e.type, e.data]), [
    ['session/end-seed', { inherited: true }], ['working-directory/change', { cwd: f.target.path }],
    ['permission/preset', { preset: 'fixture-safe' }], ['sandbox/mode', { mode: 'read-only' }], ['approval/policy', { policy: 'ask' }],
  ]);
  copy.events.forEach((e, i) => assert.equal(e.seq, i));
  assert.deepEqual(f.records.get(f.header.id), original);
  assert.deepEqual(f.archived, [f.header.id]);
  assert.deepEqual(f.target.sessionIds, [result.sessionId]);
  assert.equal(f.owned.size, 0);
  const positions = name => f.actions.findIndex(action => action[0] === name);
  assert.ok(positions('flush') < positions('replay'));
  assert.ok(positions('replay') < positions('attach'));
  assert.ok(positions('attach') < positions('archive'));
  assert.equal(f.actions.at(-1)[0], 'close');
  assert.equal(f.actions.at(-1)[1], f.header.id);
});

test('rejects invalid identifiers and absent workspace before opening persistence', async () => {
  const f = await fixture();
  await rejectsCode(moveSession(f.ctx, '../session', f.target.id), 'invalid-input');
  await rejectsCode(moveSession(f.ctx, f.header.id, 'missing'), 'workspace-not-found');
  assert.equal(f.actions.length, 0);
});

for (const liveKey of ['liveAgent', 'liveSession']) test(`refuses ${liveKey} without stopping it`, async () => {
  const f = await fixture(); f.state[liveKey] = true;
  await rejectsCode(moveSession(f.ctx, f.header.id, f.target.id), 'source-open');
  assert.equal(f.actions.length, 0);
});

test('rechecks live status after taking lock and closes acquired handle', async () => {
  const f = await fixture(); f.state.afterOpen = async () => { f.state.liveAgent = true; };
  await rejectsCode(moveSession(f.ctx, f.header.id, f.target.id), 'source-open');
  assert.equal(f.owned.size, 0);
  assert.equal(f.records.size, 1);
});

test('held native-style writer refuses transfer without releasing another owner', async () => {
  const f = await fixture();
  const held = await f.ctx.sessionPersistence.open(f.header.id, 'write');
  await assert.rejects(moveSession(f.ctx, f.header.id, f.target.id), e => e instanceof TransferError);
  assert.ok(f.owned.has(f.header.id));
  assert.equal(f.records.size, 1);
  assert.equal(f.archived.length, 0);
  await held.close();
});

for (const [name, configure, code] of [
  ['archived source', f => f.archived.push(f.header.id), 'already-archived'],
  ['same workspace', f => { f.target.path = f.header.cwd; }, 'same-workspace'],
  ['missing destination', f => { f.target.path = join(root, 'never-created'); }, undefined],
  ['background activity', f => { f.state.activity = [{ kind: 'job' }]; }, 'session-active'],
  ['only reserved presets', f => { f.state.presets = [{ value: 'auto' }, { value: 'custom' }]; }, 'permissions-unavailable'],
  ['unsupported source', f => { f.records.get(f.header.id).header.isSeeded = true; }, 'seeded-source'],
]) test(`pre-copy refusal: ${name}`, async () => {
  const f = await fixture(); configure(f);
  if (code) await rejectsCode(moveSession(f.ctx, f.header.id, f.target.id), code);
  else await assert.rejects(moveSession(f.ctx, f.header.id, f.target.id));
  assert.equal(f.records.size, 1);
  assert.equal(f.owned.size, 0);
  assert.ok(!f.actions.some(a => a[0] === 'archive'));
});

for (const fault of ['createError', 'appendError', 'flushError', 'corruptReadback', 'destinationCloseError', 'replayError', 'badCwdProjection', 'badPermissionProjection', 'attachError', 'emitError', 'archiveError']) {
  test(`partial failure ${fault} preserves source and closes handles`, async () => {
    const f = await fixture({ [fault]: true });
    const before = clone(f.records.get(f.header.id));
    let failure;
    try { await moveSession(f.ctx, f.header.id, f.target.id); } catch (error) { failure = error; }
    assert.equal(failure?.code, 'partial-transfer');
    assert.match(failure.details.copySessionId, /^session-/);
    assert.deepEqual(f.records.get(f.header.id), before);
    assert.equal(f.archived.length, 0);
    assert.equal(f.owned.size, 0);
    assert.equal(failure.details.sourceArchived, false);
    if (fault === 'archiveError' || fault === 'emitError') assert.equal(failure.details.attached, true);
  });
}

test('source close failure reports completed archival and copy identity, never pretends rollback', async () => {
  const f = await fixture({ sourceCloseError: true });
  await assert.rejects(moveSession(f.ctx, f.header.id, f.target.id), error => {
    assert.equal(error.code, 'source-close-failed');
    assert.equal(error.details.sourceArchived, true);
    assert.equal(error.details.attached, true);
    assert.ok(f.records.has(error.details.copySessionId));
    return true;
  });
  assert.deepEqual(f.archived, [f.header.id]);
});

async function httpFixture() {
  const f = await fixture();
  const browserPeer = { id: 'browser-owner' };
  const admitted = [];
  let route;
  f.ctx.connection = {
    browserPeer,
    admit(request) {
      admitted.push(request);
      // Connection owns origin/authentication checks; exercise the bridge's
      // handling of their outcomes, not a substitute authentication algorithm.
      if (request.headers.get('origin') !== 'http://localhost') return { rejection: 403 };
      return f.state.admission ?? { peer: browserPeer };
    },
    fetch: { register(value) { route = value; return () => {}; } },
  };
  f.ctx.tools = { register() { return () => {}; } };
  f.ctx.effect = callback => callback();
  f.ctx.on = () => {};
  apply(f.ctx);
  const request = (options = {}) => new Request('http://localhost/api/mainframe/workspace-transfer', {
    method: 'POST',
    headers: {
      origin: 'http://localhost',
      'content-type': 'application/json',
      'x-mainframe-workspace-transfer': '1',
      ...options.headers,
    },
    body: options.body ?? JSON.stringify({ sessionId: f.header.id, workspaceId: f.target.id }),
  });
  return { ...f, route, request, admitted, browserPeer };
}

test('HTTP bridge registers exact POST route and accepts admitted owner JSON request', async () => {
  const f = await httpFixture();
  assert.equal(f.route.path, '/api/mainframe/workspace-transfer');
  assert.deepEqual(f.route.methods, ['POST']);
  assert.equal(f.route.requestBody, 'buffered');
  const request = f.request();
  const response = await f.route.fetch(request);
  assert.equal(f.admitted[0], request);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('content-type'), 'application/json');
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
  const result = await response.json();
  assert.equal(result.ok, true);
  assert.equal(result.workspaceId, f.target.id);
  assert.notEqual(result.sessionId, f.header.id);
  assert.deepEqual(f.archived, [f.header.id]);
  assert.deepEqual(f.target.sessionIds, [result.sessionId]);
});

for (const [name, configure, options] of [
  ['rejected browser authentication', f => { f.state.admission = { rejection: 401 }; }, {}],
  ['foreign origin rejected by Connection', () => {}, { headers: { origin: 'https://other.example' } }],
  ['non-browser peer, even if separately admitted', f => { f.state.admission = { peer: { id: 'api-owner' } }; }, {}],
  ['missing custom header', () => {}, { headers: { 'x-mainframe-workspace-transfer': '' } }],
  ['wrong custom header', () => {}, { headers: { 'x-mainframe-workspace-transfer': 'true' } }],
  ['non-JSON content type', () => {}, { headers: { 'content-type': 'text/plain' } }],
]) test(`HTTP bridge refuses ${name} before opening source`, async () => {
  const f = await httpFixture(); configure(f);
  const response = await f.route.fetch(f.request(options));
  assert.equal(response.status, 403);
  assert.equal(await response.text(), '');
  assert.equal(f.admitted.length, 1);
  assert.equal(f.actions.length, 0);
  assert.equal(f.records.size, 1);
});

for (const [name, body, status] of [
  ['malformed JSON', '{', 400],
  ['null body', 'null', 400],
  ['caller-supplied action', JSON.stringify({ action: 'self_test' }), 400],
  ['unknown input field', JSON.stringify({ sessionId: 'session-source', workspaceId: 'workspace-target', extra: true }), 400],
  ['oversized body', ' '.repeat(4097), 413],
]) test(`HTTP bridge refuses ${name} before opening source`, async () => {
  const f = await httpFixture();
  const response = await f.route.fetch(f.request({ body }));
  assert.equal(response.status, status);
  assert.equal(f.actions.length, 0);
  assert.equal(f.records.size, 1);
});

test('HTTP bridge returns sanitized source-open JSON without creating or archiving', async () => {
  const f = await httpFixture();
  f.state.liveAgent = true;
  const response = await f.route.fetch(f.request());
  assert.equal(response.status, 200, 'expected domain refusals use the JSON result envelope');
  assert.deepEqual(await response.json(), {
    ok: false,
    error: { code: 'source-open', message: 'Close this conversation before moving it. Idle is not enough.' },
  });
  assert.equal(f.actions.length, 0);
  assert.equal(f.records.size, 1);
  assert.deepEqual(f.archived, []);
});

test('apply shutdown waits for admitted work, rejects new work, and serializes queued actions', async () => {
  const f = await fixture();
  let release, entered;
  const gate = new Promise(resolve => { release = resolve; });
  const started = new Promise(resolve => { entered = resolve; });
  f.state.sourceRead = async () => { entered(); await gate; };
  let tool, dispose;
  f.ctx.connection = { fetch: { register() { return () => {}; } } };
  f.ctx.tools = { register(value) { tool = value; return () => {}; } };
  f.ctx.effect = callback => callback();
  f.ctx.on = (name, callback) => { if (name === 'dispose') dispose = callback; };
  apply(f.ctx);
  const moving = tool.execute({ action: 'move', sessionId: f.header.id, workspaceId: f.target.id });
  await started;
  let listed = false;
  const listing = tool.execute({ action: 'list' }).then(value => { listed = true; return value; });
  const stopping = dispose();
  assert.equal(listed, false);
  await rejectsCode(tool.execute({ action: 'list' }), 'closing');
  release();
  assert.equal((await moving).ok, true);
  assert.equal((await listing).ok, true);
  await stopping;
  assert.equal(f.owned.size, 0);
});
