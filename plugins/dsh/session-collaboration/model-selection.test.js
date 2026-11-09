import test from 'node:test';
import assert from 'node:assert/strict';
import { createModelSelection, requestedSelection } from './model-selection.js';
import { createLifecycleManagement } from './lifecycle-management.js';
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function fixture() {
  const calls = [], sender = { id: 'caller' }, recorded = [];
  let selection = { provider: 'p', model: 'm', reasoningEffort: 'high' };
  const target = { id: 'target', status: 'running', session: { header: {} }, model: {
    current: () => ({ ...selection }), select: value => { calls.push('select'); selection = { ...value }; recorded.push({ type: 'model/selection', selection }); }
  } };
  const live = new Map([['caller', sender], ['target', target]]);
  const rows = [{ sessionId: 'target' }, { sessionId: 'cold' }, { sessionId: 'archived', archived: true }, { sessionId: 'child', origin: 'subagent' }];
  const ctx = { llm: {
    listProviders: () => [{ id: 'p', name: 'Provider' }],
    listModels: async () => [{ id: 'm', name: 'Model' }, { id: 'no-reason', name: 'Plain' }],
    resolveModelInfo: async (_p, model) => ({ id: model, ...(model === 'm' ? { reasoning: { efforts: [{ id: 'low', name: 'Low' }, { id: 'high', name: 'High' }], defaultEffort: 'low' } } : {}) }),
    resolveCallConfig: async value => {
      calls.push('validate');
      if (value.reasoningEffort !== undefined && (value.model !== 'm' || !['low', 'high'].includes(value.reasoningEffort))) throw new Error('unsupported effort');
      return { ...value, reasoningEffort: value.reasoningEffort ?? 'low' };
    }
  }, agents: { get: id => live.get(id) }, workspaceRegistry: { archivedSessionIds: ['archived'], get: id => id === 'project' ? workspace : undefined },
  sessionController: {
    list: async () => ({ items: rows }),
    create: async () => { calls.push('create'); return { sessionId: 'fresh' }; },
    resolveAgent: async id => { calls.push('resolve'); const agent = id === 'target' ? target : { ...target, id }; live.set(id, agent); return { agent }; },
    selectModel: () => assert.fail('global-default API forbidden'), prompt: () => assert.fail('no model run')
  }, agentDefaultModel: { saveSelection: () => assert.fail('no global defaults') } };
  const workspace = { status: async () => 'ok' };
  return { ctx, calls, sender, target, rows, live, recorded, api: createLifecycleManagement(ctx), exec: { agent: sender } };
}
const choice = { provider: 'p', model: 'm' };
test('progressive bounded discovery exposes exact model efforts and no invented defaults', async () => {
  const f = fixture(), api = createModelSelection(f.ctx);
  assert.equal((await api.models()).kind, 'providers');
  const page = await api.models({ provider: 'p', limit: 1 });
  assert.deepEqual(page.items, [{ id: 'm', name: 'Model' }]); assert.equal(page.nextOffset, 1);
  const efforts = await api.models({ ...choice });
  assert.equal(efforts.kind, 'efforts'); assert.equal(efforts.defaultEffort, 'low'); assert.equal(efforts.items.length, 2);
  const plain = await api.models({ provider: 'p', model: 'no-reason' });
  assert.deepEqual(plain.items, []); assert.equal('defaultEffort' in plain, false);
  for (const args of [null, [], { model: 'm' }, { offset: -1 }, { limit: 101 }, { extra: true }]) await assert.rejects(api.models(args), { code: 'invalid-input' });
  for (const args of [{ provider: 'bad' }, { provider: 'p', model: 'bad' }]) await assert.rejects(api.models(args), { code: 'model-unavailable' });
});
test('complete selection requires pair and rejects malformed effort', () => {
  for (const args of [{ provider: 'p' }, { model: 'm' }, { reasoning_effort: 'low' }, { ...choice, reasoning_effort: '' }, { ...choice, model: null }])
    assert.throws(() => requestedSelection(args), { code: 'invalid-input' });
  assert.equal(requestedSelection({}), undefined);
});
test('running set persists complete choice without inheriting effort or touching defaults/run', async () => {
  const f = fixture();
  const result = await f.api.session({ action: 'set_model', sessionId: 'target', ...choice }, f.exec);
  assert.deepEqual(result.selection, choice); assert.equal(result.defaultChanged, false); assert.equal(result.appliedFrom, 'next-unprepared-step');
  assert.deepEqual(f.target.model.current(), choice); assert.deepEqual(f.recorded[0], { type: 'model/selection', selection: choice });
  await f.api.session({ action: 'set_model', sessionId: 'target', ...choice, reasoning_effort: 'high' }, f.exec);
  assert.equal(f.target.model.current().reasoningEffort, 'high');
});
test('passive model reads do not resolve cold Agents or invent defaults', async () => {
  const f = fixture();
  assert.equal((await f.api.session({ action: 'get_model', sessionId: 'target' }, f.exec)).selection.reasoningEffort, 'high');
  const cold = await f.api.session({ action: 'get_model', sessionId: 'cold' }, f.exec);
  assert.equal(cold.outcome, 'unknown'); assert.equal(cold.loaded, false); assert.equal('selection' in cold, false); assert.deepEqual(f.calls, []);
});
test('invalid create route/effort fails before creating; selected create retains fresh identity', async () => {
  const f = fixture();
  for (const bad of [{ provider: 'bad', model: 'm' }, { provider: 'p', model: 'missing' }, { ...choice, reasoning_effort: 'fake' }, { provider: 'p', model: 'no-reason', reasoning_effort: 'high' }]) {
    await assert.rejects(f.api.session({ action: 'create', workspaceId: 'project', ...bad }, f.exec), { code: 'model-unavailable' });
    assert.equal(f.calls.includes('create'), false);
  }
  const result = await f.api.session({ action: 'create', workspaceId: 'project', ...choice }, f.exec);
  assert.equal(result.sessionId, 'fresh'); assert.deepEqual(result.selection, choice);
});
test('configuration failure preserves created ID and never retries creation', async () => {
  const f = fixture(); f.target.model.select = () => { throw new Error('append uncertain'); };
  const result = await f.api.session({ action: 'create', workspaceId: 'project', ...choice }, f.exec);
  assert.equal(result.sessionId, 'fresh'); assert.equal(result.outcome, 'created-model-unknown'); assert.equal(f.calls.filter(x => x === 'create').length, 1);
  assert.equal((await f.api.session({ action: 'set_model', sessionId: 'target', ...choice }, f.exec)).outcome, 'unknown');
});
test('model actions reject self/subagents and set rejects archived targets before resolve', async () => {
  const f = fixture();
  for (const action of ['get_model', 'set_model']) for (const [sessionId, code] of [['caller', 'self-target'], ['child', 'subagent-target']])
    await assert.rejects(f.api.session({ action, sessionId, ...(action === 'set_model' ? choice : {}) }, f.exec), { code });
  await assert.rejects(f.api.session({ action: 'set_model', sessionId: 'archived', ...choice }, f.exec), { code: 'archived-target' });
  assert.deepEqual(f.calls, []);
});
test('disposal drains admitted selection, rejects new calls, and cancellation does not abandon its result', async () => {
  const f = fixture(), entered = deferred(), finish = deferred(), abort = new AbortController();
  f.target.model.select = async () => { entered.resolve(); await finish.promise; };
  const task = f.api.session({ action: 'set_model', sessionId: 'target', ...choice }, { ...f.exec, signal: abort.signal });
  await entered.promise; abort.abort(); let disposed = false; const disposal = f.api.dispose().then(() => disposed = true);
  await Promise.resolve(); assert.equal(disposed, false);
  await assert.rejects(f.api.session({ action: 'get_model', sessionId: 'target' }, f.exec), /unloaded/);
  await assert.rejects(f.api.models({}, f.exec), /unloaded/);
  finish.resolve(); assert.equal((await task).outcome, 'selected'); await disposal;
});
test('public resolve failure union preserves creation identity without selecting', async () => {
  const f = fixture(); f.ctx.sessionController.resolveAgent = async () => ({ error: new Error('private detail') });
  const created = await f.api.session({ action: 'create', workspaceId: 'project', ...choice }, f.exec);
  assert.equal(created.outcome, 'created-model-unknown'); assert.equal(created.sessionId, 'fresh');
  const set = await f.api.session({ action: 'set_model', sessionId: 'cold', ...choice }, f.exec);
  assert.equal(set.outcome, 'unknown'); assert.equal(f.calls.includes('select'), false);
  assert.equal(JSON.stringify([created, set]).includes('private detail'), false);
});
test('archive during initial model validation prevents cold Agent resolution', async () => {
  const f = fixture();
  f.ctx.llm.resolveCallConfig = async value => { f.ctx.workspaceRegistry.archivedSessionIds.push('cold'); return value; };
  await assert.rejects(f.api.session({ action: 'set_model', sessionId: 'cold', ...choice }, f.exec), { code: 'archived-target' });
  assert.equal(f.calls.includes('resolve'), false); assert.equal(f.calls.includes('select'), false); assert.equal(f.live.has('cold'), false);
});
test('final public identity and archive checks reject changes during validation', async () => {
  for (const change of [f => f.live.delete('target'), f => f.ctx.workspaceRegistry.archivedSessionIds.push('target')]) {
    const f = fixture(); let validations = 0;
    f.ctx.llm.resolveCallConfig = async value => { if (++validations === 2) change(f); return value; };
    const result = await f.api.session({ action: 'set_model', sessionId: 'target', ...choice }, f.exec);
    assert.equal(result.outcome, 'unknown'); assert.equal(f.calls.includes('select'), false);
  }
});
test('concurrent selections install complete choices without mixed effort fields', async () => {
  const f = fixture();
  const results = await Promise.all([
    f.api.session({ action: 'set_model', sessionId: 'target', ...choice, reasoning_effort: 'high' }, f.exec),
    f.api.session({ action: 'set_model', sessionId: 'target', provider: 'p', model: 'no-reason' }, f.exec)
  ]);
  assert.equal(results.every(result => result.outcome === 'selected'), true);
  assert.deepEqual(f.recorded.map(row => row.selection), [{ ...choice, reasoningEffort: 'high' }, { provider: 'p', model: 'no-reason' }]);
});
test('noncooperative read-only model metadata cannot hold teardown or admit mutations later', { timeout: 1000 }, async () => {
  for (const mode of ['models', 'efforts', 'create-catalog', 'set-catalog', 'create-validation', 'set-validation']) {
    const f = fixture(), entered = deferred(); let reject;
    const pending = new Promise((_, no) => { reject = no; });
    const read = () => { entered.resolve(); return pending; };
    if (mode === 'efforts') f.ctx.llm.resolveModelInfo = read;
    else if (mode.endsWith('validation')) f.ctx.llm.resolveCallConfig = read;
    else f.ctx.llm.listModels = read;
    const task = ['models', 'efforts'].includes(mode) ? f.api.models(mode === 'efforts' ? choice : { provider: 'p' }, f.exec)
      : f.api.session(mode.startsWith('create') ? { action: 'create', workspaceId: 'project', ...choice }
        : { action: 'set_model', sessionId: 'target', ...choice }, f.exec);
    await entered.promise; const rejected = assert.rejects(task, /unloaded/);
    await f.api.dispose(); await rejected;
    reject(new Error('late metadata rejection')); await Promise.resolve();
    assert.equal(f.calls.some(call => ['create', 'resolve', 'select'].includes(call)), false);
  }
});
test('teardown cancels stalled post-mutation revalidation while retaining native identity', { timeout: 1000 }, async () => {
  for (const mode of ['create', 'set_model']) for (const method of ['listModels', 'resolveCallConfig']) {
    const f = fixture(), entered = deferred(); let reject, reads = 0;
    const native = f.ctx.llm[method];
    const pending = new Promise((_, no) => { reject = no; });
    f.ctx.llm[method] = (...args) => {
      if (++reads === 1) return native(...args);
      entered.resolve(); return pending;
    };
    const task = f.api.session(mode === 'create' ? { action: mode, workspaceId: 'project', ...choice }
      : { action: mode, sessionId: 'cold', ...choice }, f.exec);
    await entered.promise; await f.api.dispose();
    const result = await task;
    assert.equal(result.outcome, mode === 'create' ? 'created-model-unknown' : 'unknown');
    assert.equal(result.sessionId, mode === 'create' ? 'fresh' : 'cold');
    assert.equal(f.calls.filter(call => call === 'resolve').length, 1); assert.equal(f.calls.includes('select'), false);
    reject(new Error('late post-mutation read rejection')); await Promise.resolve();
  }
});
test('teardown still drains native Agent activation before returning a partial outcome', async () => {
  for (const mode of ['create', 'set_model']) {
    const f = fixture(), entered = deferred(), finish = deferred();
    f.ctx.sessionController.resolveAgent = () => { entered.resolve(); return finish.promise; };
    const task = f.api.session(mode === 'create' ? { action: mode, workspaceId: 'project', ...choice }
      : { action: mode, sessionId: 'target', ...choice }, f.exec);
    await entered.promise; let disposed = false; const disposal = f.api.dispose().then(() => { disposed = true; });
    await Promise.resolve(); assert.equal(disposed, false);
    finish.resolve({ agent: mode === 'create' ? { ...f.target, id: 'fresh' } : f.target });
    const result = await task; await disposal;
    assert.equal(result.outcome, mode === 'create' ? 'created-model-unknown' : 'unknown'); assert.equal(f.calls.includes('select'), false);
  }
});
test('model recovery guidance only names the consolidated collaboration tool', async () => {
  assert.throws(() => requestedSelection({ model: 'm' }), error => {
    assert.match(error.message, /collaboration action models/); assert.doesNotMatch(error.message, /collaboration_models/); return true;
  });
  const f = fixture();
  for (const value of [{ provider: 'missing', model: 'm' }, { provider: 'p', model: 'missing' }, { ...choice, reasoningEffort: 'missing' }])
    await assert.rejects(createModelSelection(f.ctx).validate(value), error => {
      assert.match(error.message, /collaboration action models/); assert.doesNotMatch(error.message, /collaboration_models/); return true;
    });
});
test('unload during prevalidation blocks resolve/create, registry validation failures stay sanitized', async () => {
  const f = fixture(), gate = deferred(); f.ctx.llm.resolveCallConfig = () => gate.promise;
  const task = f.api.session({ action: 'create', workspaceId: 'project', ...choice }, f.exec);
  await Promise.resolve(); const disposal = f.api.dispose(); gate.resolve(choice);
  await assert.rejects(task, /unloaded/); await disposal; assert.equal(f.calls.includes('create'), false);
});
