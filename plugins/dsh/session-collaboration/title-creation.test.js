import test from 'node:test';
import assert from 'node:assert/strict';
import { createLifecycleManagement } from './lifecycle-management.js';
import { validateCollaboration } from './tool-surface.js';

const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function fixture() {
  const calls = [], events = [], sender = { id: 'caller' };
  const target = { id: 'fresh', session: { id: 'fresh', header: {} }, model: { select: value => calls.push(['select', value]) } };
  const live = new Map([['caller', sender], ['fresh', target]]);
  const workspace = { status: async () => 'ok' };
  // Injected pure native normalizer: the adapter uses its answer, not a duplicate sanitizer.
  const normalizeTitle = (text, maxBytes) => { calls.push(['normalize', text, maxBytes]); return text === '\u200b' ? '' : text.trim().replace(/\s+/gu, ' '); };
  const ctx = {
    agents: { get: id => live.get(id) },
    workspaceRegistry: { get: id => id === 'project' ? workspace : undefined, archivedSessionIds: [] },
    sessionController: {
      create: async args => { calls.push(['create', args]); return { sessionId: 'fresh' }; },
      resolveAgent: async id => { calls.push(['resolve', id]); return { agent: target }; },
      prompt: () => assert.fail('must not prompt'), resumeGoal: () => assert.fail('must not rearm')
    },
    sessionTitle: { rename: (session, title) => {
      assert.equal(session, target.session); calls.push(['rename', title]);
      title = title.trim().replace(/\s+/gu, ' ');
      // Native may truncate further according to its configured byte limit.
      const snapshot = { title: title.slice(0, 8), source: { kind: 'user' } };
      events.push({ type: 'session/title', ...snapshot }); return snapshot;
    } },
    llm: {
      listProviders: () => [{ id: 'p', name: 'P' }], listModels: async () => [{ id: 'm', name: 'M' }],
      resolveCallConfig: async value => value
    }
  };
  return { ctx, calls, events, sender, target, live, api: createLifecycleManagement(ctx, { normalizeTitle }), exec: { agent: sender } };
}
const args = { action: 'create', workspaceId: 'project', title: '  Named   session  ' };
const choice = { provider: 'p', model: 'm' };

test('create names the exact new session via native rename and returns accepted title without input', async () => {
  const f = fixture(), result = await f.api.session(args, f.exec);
  assert.equal(result.outcome, 'created'); assert.equal(result.sessionId, 'fresh');
  assert.equal(result.title, 'Named se'); assert.equal(result.titleStatus, 'applied');
  assert.deepEqual(f.calls, [['normalize', args.title, Number.MAX_SAFE_INTEGER], ['create', { workspaceId: 'project' }], ['resolve', 'fresh'], ['rename', args.title]]);
  assert.deepEqual(f.events.map(e => e.type), ['session/title']); await f.api.dispose();
});
test('invalid title or action rejects before creating or resolving a session', async () => {
  const f = fixture();
  for (const title of [null, true, 4, '', '  ', 'x'.repeat(201), '\u200b'])
    await assert.rejects(f.api.session({ ...args, title }, f.exec), { code: 'invalid-input' });
  for (const action of ['archive', 'unarchive', 'get_model', 'set_model'])
    await assert.rejects(f.api.session({ action, sessionId: 'target', title: 'Name', ...(action === 'set_model' ? choice : {}) }, f.exec), { code: 'invalid-input' });
  assert.equal(f.calls.some(([name]) => ['create', 'resolve', 'rename'].includes(name)), false);
});
test('title bounds count Unicode code points at both public and lifecycle boundaries', async () => {
  const f = fixture(), valid = { ...args, title: '🚀'.repeat(200) }, invalid = { ...args, title: '🚀'.repeat(201) };
  assert.doesNotThrow(() => validateCollaboration(valid));
  assert.equal((await f.api.session(valid, f.exec)).titleStatus, 'applied');
  assert.throws(() => validateCollaboration(invalid), { code: 'invalid-input' });
  await assert.rejects(f.api.session(invalid, f.exec), { code: 'invalid-input' });
  assert.equal(f.calls.filter(([name]) => name === 'create').length, 1);
});
test('unavailable native title capability fails before creation', async () => {
  const f = fixture(); delete f.ctx.sessionTitle;
  await assert.rejects(f.api.session(args, f.exec), { code: 'title-unavailable' });
  assert.equal(f.calls.some(([name]) => name === 'create'), false);
});
test('title and model outcomes remain independent and never recreate after partial failure', async () => {
  for (const titleFails of [false, true]) for (const modelFails of [false, true]) {
    const f = fixture();
    if (titleFails) {
      const rename = f.ctx.sessionTitle.rename;
      f.ctx.sessionTitle.rename = (...values) => { rename(...values); throw new Error('private failure after append'); };
    }
    if (modelFails) f.target.model.select = () => { throw new Error('private failure'); };
    const result = await f.api.session({ ...args, ...choice }, f.exec);
    assert.equal(result.sessionId, 'fresh');
    assert.equal(result.outcome, titleFails ? modelFails ? 'created-configuration-unknown' : 'created-title-unknown' : modelFails ? 'created-model-unknown' : 'created');
    assert.equal(result.titleStatus, titleFails ? 'unknown' : 'applied');
    assert.equal(result.title, titleFails ? undefined : 'Named se');
    assert.deepEqual(result.selection, modelFails ? undefined : choice);
    assert.equal(f.calls.filter(([name]) => name === 'create').length, 1);
    assert.equal(f.calls.filter(([name]) => name === 'resolve').length, 1);
    assert.equal(f.calls.filter(([name]) => name === 'rename').length, 1);
    assert.equal(f.events.length, 1);
    assert.equal(JSON.stringify(result).includes('private failure'), false);
  }
});
test('resolve failure, identity replacement, subagent or archive cannot rename another target', async () => {
  for (const mode of ['error', 'wrong-id', 'wrong-session', 'missing-session', 'replaced', 'subagent', 'archived']) {
    const f = fixture();
    if (mode === 'error') f.ctx.sessionController.resolveAgent = async () => ({ error: new Error('private') });
    if (mode === 'wrong-id') f.target.id = 'other';
    if (mode === 'wrong-session') f.target.session.id = 'other';
    if (mode === 'missing-session') delete f.target.session;
    if (mode === 'replaced') f.live.set('fresh', { ...f.target });
    if (mode === 'subagent') f.target.session.header.origin = 'subagent';
    if (mode === 'archived') f.ctx.workspaceRegistry.archivedSessionIds.push('fresh');
    const result = await f.api.session(args, f.exec);
    assert.equal(result.outcome, 'created-title-unknown'); assert.equal(result.sessionId, 'fresh');
    assert.equal(result.titleStatus, 'unknown'); assert.deepEqual(f.events, []);
    assert.equal(f.calls.filter(([name]) => name === 'create').length, 1);
  }
});
test('preflight cancellation never creates, admitted cancellation preserves naming and identity', { timeout: 1000 }, async () => {
  const f = fixture(), abort = new AbortController(); abort.abort();
  await assert.rejects(f.api.session(args, { ...f.exec, signal: abort.signal })); assert.deepEqual(f.calls, []);
  const g = fixture(), admitted = deferred(), finish = deferred(), cancel = new AbortController();
  g.ctx.sessionController.create = async () => { admitted.resolve(); await finish.promise; return { sessionId: 'fresh' }; };
  const task = g.api.session(args, { ...g.exec, signal: cancel.signal });
  await admitted.promise; cancel.abort(); finish.resolve();
  assert.equal((await task).titleStatus, 'applied'); assert.equal(g.events.length, 1);
});
test('native creation failures never resolve or rename, preserving explicit attachment identity', async () => {
  for (const attached of [false, true]) {
    const f = fixture();
    f.ctx.sessionController.create = async () => { f.calls.push(['create']); throw attached
      ? { isDSHRemoteError: true, code: 'session/workspace-attach-failed', details: { workspaceId: 'project', sessionId: 'fresh' } }
      : new Error('private'); };
    const result = await f.api.session(args, f.exec);
    assert.equal(result.outcome, attached ? 'created-unattached' : 'unknown');
    assert.equal(result.sessionId, attached ? 'fresh' : undefined);
    assert.equal(f.calls.filter(([name]) => name === 'create').length, 1);
    assert.equal(f.calls.some(([name]) => name === 'resolve' || name === 'rename'), false);
  }
});
test('disposal during native create drains identity without starting configuration', { timeout: 1000 }, async () => {
  const f = fixture(), admitted = deferred(), finish = deferred();
  f.ctx.sessionController.create = async () => { admitted.resolve(); return finish.promise; };
  const task = f.api.session({ ...args, ...choice }, f.exec); await admitted.promise;
  const disposal = f.api.dispose(); finish.resolve({ sessionId: 'fresh' });
  const result = await task; await disposal;
  assert.equal(result.sessionId, 'fresh'); assert.equal(result.outcome, 'created-configuration-unknown');
  assert.equal(f.calls.some(([name]) => ['resolve', 'rename', 'select'].includes(name)), false);
});
test('disposal during model revalidation preserves an accepted title without selecting', { timeout: 1000 }, async () => {
  const f = fixture(), entered = deferred(); let reads = 0;
  f.ctx.llm.listModels = () => ++reads === 1 ? [{ id: 'm', name: 'M' }] : (entered.resolve(), new Promise(() => {}));
  const task = f.api.session({ ...args, ...choice }, f.exec); await entered.promise;
  await f.api.dispose(); const result = await task;
  assert.equal(result.sessionId, 'fresh'); assert.equal(result.outcome, 'created-model-unknown');
  assert.equal(result.title, 'Named se'); assert.equal(result.titleStatus, 'applied');
  assert.equal(f.calls.some(([name]) => name === 'select'), false);
});
test('disposal drains admitted resolution, preserves created ID and stops late naming', { timeout: 1000 }, async () => {
  const f = fixture(), admitted = deferred(), finish = deferred();
  f.ctx.sessionController.resolveAgent = async () => { admitted.resolve(); return finish.promise; };
  const task = f.api.session(args, f.exec); await admitted.promise;
  let disposed = false; const disposal = f.api.dispose().then(() => { disposed = true; });
  await Promise.resolve(); assert.equal(disposed, false);
  finish.resolve({ agent: f.target });
  const result = await task; await disposal;
  assert.equal(result.sessionId, 'fresh'); assert.equal(result.outcome, 'created-title-unknown');
  assert.deepEqual(f.events, []);
});
