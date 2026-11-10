import test from 'node:test';
import assert from 'node:assert/strict';
import { createLifecycleManagement } from './lifecycle-management.js';

function fixture() {
  const calls = [], sender = { id: 'caller' }, target = { id: 'target', status: 'idle', inbox: { hasPending: false }, session: { header: {} } };
  const agents = new Map([[sender.id, sender], [target.id, target]]);
  const workspace = { id: 'project', sessionIds: [], status: async () => 'ok' };
  const ctx = { agents: { get: id => agents.get(id) }, workspaceRegistry: {
    get: id => id === workspace.id ? workspace : undefined,
    archivedSessionIds: [],
    archiveSession: async (...args) => { calls.push(['archive', ...args]); },
    unarchiveSession: async (...args) => { calls.push(['unarchive', ...args]); }
  }, sessionController: {
    list: async () => ({ items: [{ sessionId: 'target' }, { sessionId: 'child', origin: 'subagent' }, { sessionId: 'fork', parentSessionId: 'parent' }] }),
    state: async ({ sessionId }) => ({ active: agents.has(sessionId), running: agents.get(sessionId)?.status === 'running',
      queue: agents.has(sessionId) ? [] : null, pendingInput: [] }),
    create: async (...args) => { calls.push(['create', ...args]); return { sessionId: 'fresh', agentPreset: 'native-default' }; },
    resolveAgent: () => assert.fail('must not activate'), prompt: () => assert.fail('must not prompt'),
    resumeGoal: () => assert.fail('must not rearm goals')
  } };
  return { ctx, calls, sender, target, agents, workspace, api: createLifecycleManagement(ctx), exec: { agent: sender } };
}
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };

test('create in empty existing project passes only workspaceId and returns native identity/default', async () => {
  const f = fixture();
  assert.deepEqual(await f.api.session({ action: 'create', workspaceId: 'project' }, f.exec),
    { action: 'create', outcome: 'created', workspaceId: 'project', sessionId: 'fresh', agentPreset: 'native-default' });
  assert.deepEqual(f.calls, [['create', { workspaceId: 'project' }]]);
  await f.api.dispose();
});
test('unknown or missing-directory projects never reach native create', async () => {
  const f = fixture();
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'missing' }, f.exec), { code: 'workspace-not-found' });
  f.workspace.status = async () => 'missing-dir';
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'project' }, f.exec), { code: 'workspace-unavailable' });
  assert.deepEqual(f.calls, []);
});
test('invalid and force/reuse/ancestry/preset/title fields fail before mutation', async () => {
  const f = fixture();
  const bad = [{}, null, [], { action: 'delete' }, { action: 'create' }, { action: 'unarchive' },
    { action: 'create', workspaceId: '../x' }, { action: 'create', workspaceId: 'project', sessionId: 'target' },
    { action: 'unarchive', sessionId: 'target', workspaceId: 'project' },
    ...['force', 'stopActivity', 'cwd', 'parentSessionId', 'origin', 'agentPreset', 'title'].map(key =>
      ({ action: 'create', workspaceId: 'project', [key]: true }))];
  for (const args of bad) await assert.rejects(f.api.session(args, f.exec), { code: 'invalid-input' });
  assert.deepEqual(f.calls, []);
});
test('self, missing and subagent lifecycle targets are rejected', async () => {
  const f = fixture();
  for (const action of ['archive', 'unarchive']) {
    for (const [sessionId, code] of [['caller', 'self-target'], ['missing', 'session-not-found'], ['child', 'subagent-target']])
      await assert.rejects(f.api.session({ action, sessionId }, f.exec), { code });
  }
  f.target.session.header.origin = 'subagent';
  await assert.rejects(f.api.session({ action: 'unarchive', sessionId: 'target' }, f.exec), { code: 'subagent-target' });
  assert.deepEqual(f.calls, []);
});
test('archive uses native no-force primitive for idle, cold and ordinary fork targets', async () => {
  const f = fixture();
  for (const sessionId of ['target', 'target', 'fork']) {
    const result = await f.api.session({ action: 'archive', sessionId }, f.exec);
    assert.equal(result.outcome, 'archived'); assert.equal(result.archived, true);
    assert.equal(result.archiveSafety, 'native-inactivity-snapshot');
    assert.match(result.note, /not an atomic lock/); assert.match(result.note, /consumed before commitment/);
    f.agents.delete('target');
  }
  assert.deepEqual(f.calls, [['archive', 'target'], ['archive', 'target'], ['archive', 'fork']]);
});
test('already archived target is explicitly a no-check idempotent native operation', async () => {
  const f = fixture(); f.ctx.workspaceRegistry.archivedSessionIds.push('target');
  f.target.status = 'running'; f.ctx.sessionController.state = () => assert.fail('not an inactivity check');
  const result = await f.api.session({ action: 'archive', sessionId: 'target' }, f.exec);
  assert.equal(result.outcome, 'already-archived'); assert.equal(result.archiveSafety, 'already-archived-no-check');
  assert.deepEqual(f.calls, [['archive', 'target']]);
});
test('running, queued, pending-input and nonidle targets are refused before mutation', async () => {
  for (const mode of ['running', 'maintenance', 'queue', 'approval', 'question', 'live-inbox']) {
    const f = fixture();
    if (['running', 'maintenance'].includes(mode)) f.target.status = mode;
    if (mode === 'live-inbox') f.target.inbox.hasPending = true;
    if (mode === 'queue') f.ctx.sessionController.state = async () => ({ running: false, queue: [{ content: 'private' }], pendingInput: [] });
    if (['approval', 'question'].includes(mode)) f.ctx.sessionController.state = async () => ({ running: false, queue: [], pendingInput: [mode] });
    const result = await f.api.session({ action: 'archive', sessionId: 'target' }, f.exec);
    assert.equal(result.outcome, 'busy'); assert.doesNotMatch(JSON.stringify(result), /private/); assert.deepEqual(f.calls, []);
  }
});
test('native activity families produce bounded sanitized busy refusal without stop or rollback', async () => {
  for (const kind of ['turn', 'job', 'subagent', 'schedule', 'private-custom']) {
    const f = fixture(); f.ctx.workspaceRegistry.archiveSession = async (...args) => {
      f.calls.push(['archive', ...args]);
      throw { name: 'WorkspaceActiveSessionError', sessionId: 'target', message: 'private',
        activity: [{ kind, description: 'private', id: 'private' }] };
    };
    const result = await f.api.session({ action: 'archive', sessionId: 'target' }, f.exec);
    assert.equal(result.outcome, 'busy'); assert.deepEqual(result.activityKinds, [kind === 'private-custom' ? 'other' : kind]);
    assert.doesNotMatch(JSON.stringify(result), /private/); assert.deepEqual(f.calls, [['archive', 'target']]);
  }
});
test('archive unknown failure never claims success, retries, rolls back or leaks native details', async () => {
  const f = fixture(); f.ctx.workspaceRegistry.archiveSession = async (...args) => {
    f.calls.push(['archive', ...args]); throw new Error('private');
  };
  const result = await f.api.session({ action: 'archive', sessionId: 'target' }, f.exec);
  assert.equal(result.outcome, 'unknown'); assert.equal(result.archived, undefined);
  assert.match(result.warning, /do not automatically retry or unarchive/);
  assert.doesNotMatch(JSON.stringify(result), /private/); assert.deepEqual(f.calls, [['archive', 'target']]);
});
test('native unknown-session admission rejects rather than claiming archive success', async () => {
  const f = fixture(); f.ctx.workspaceRegistry.archiveSession = async () => {
    throw { name: 'WorkspaceUnknownSessionError', sessionId: 'target', message: 'private' };
  };
  await assert.rejects(f.api.session({ action: 'archive', sessionId: 'target' }, f.exec), { code: 'session-not-found' });
});
test('archive preflight rechecks caller, target, cancellation and live inbox before admission', async () => {
  for (const mode of ['caller', 'target', 'subagent', 'cancel', 'inbox']) {
    const f = fixture(), entered = deferred(), state = deferred(), abort = new AbortController();
    f.ctx.sessionController.state = () => { entered.resolve(); return state.promise; };
    const task = f.api.session({ action: 'archive', sessionId: 'target' }, { ...f.exec, signal: abort.signal });
    await entered.promise;
    if (mode === 'caller') f.agents.set('caller', { id: 'caller' });
    if (mode === 'target') f.agents.set('target', { ...f.target });
    if (mode === 'subagent') f.target.session.header.origin = 'subagent';
    if (mode === 'cancel') abort.abort(new Error('cancelled'));
    if (mode === 'inbox') f.target.inbox.hasPending = true;
    state.resolve({ running: false, queue: [], pendingInput: [] });
    if (mode === 'inbox') assert.equal((await task).outcome, 'busy'); else await assert.rejects(task);
    assert.deepEqual(f.calls, []);
  }
});
test('source-backed native snapshot/write race remains visible, without false idle guarantee or rollback', async () => {
  const f = fixture(), snapshot = deferred(), write = deferred();
  let claimed = false, committedInput = false, blocked = false;
  // DSH 0.2.2-rc.1 workspace archiveSession checks activity before await setState;
  // agent-loop preStep claims inbox before the controller archived-session gate.
  // This models that ordering, not a private-runtime integration or atomic fix.
  f.ctx.workspaceRegistry.archiveSession = async (...args) => {
    f.calls.push(['archive', ...args]); assert.equal(f.target.status, 'idle'); snapshot.resolve();
    await write.promise; f.ctx.workspaceRegistry.archivedSessionIds.push('target');
  };
  const task = f.api.session({ action: 'archive', sessionId: 'target' }, f.exec);
  await snapshot.promise;
  f.target.status = 'running'; f.target.inbox.hasPending = true;
  // A racing next-turn claim consumes input before durable user-message commit.
  claimed = true; f.target.inbox.hasPending = false;
  write.resolve(); const result = await task;
  if (f.ctx.workspaceRegistry.archivedSessionIds.includes('target')) blocked = true; else committedInput = true;
  assert.equal(result.outcome, 'archived'); assert.equal(claimed, true); assert.equal(blocked, true); assert.equal(committedInput, false);
  assert.equal(result.archiveSafety, 'native-inactivity-snapshot'); assert.match(result.note, /racing turn\/input can be blocked or consumed/);
  assert.deepEqual(f.calls, [['archive', 'target']]);
});
test('dispose drains admitted native archive despite cancellation and reports the actual result', async () => {
  const f = fixture(), entered = deferred(), native = deferred(), abort = new AbortController();
  f.ctx.workspaceRegistry.archiveSession = (...args) => { f.calls.push(['archive', ...args]); entered.resolve(); return native.promise; };
  const task = f.api.session({ action: 'archive', sessionId: 'target' }, { ...f.exec, signal: abort.signal });
  await entered.promise; abort.abort(); let disposed = false;
  const disposal = f.api.dispose().then(() => { disposed = true; });
  await Promise.resolve(); assert.equal(disposed, false);
  native.resolve(); assert.equal((await task).outcome, 'archived'); await disposal;
  assert.deepEqual(f.calls, [['archive', 'target']]);
});
test('uncooperative preflight reads do not block teardown or later mutate', { timeout: 1000 }, async () => {
  for (const mode of ['status', 'list', 'state']) {
    const f = fixture(), entered = deferred(); let reject;
    const pending = new Promise((_, no) => { reject = no; });
    const read = () => { entered.resolve(); return pending; };
    if (mode === 'status') f.workspace.status = read;
    if (mode === 'list') f.ctx.sessionController.list = read;
    if (mode === 'state') f.ctx.sessionController.state = read;
    const task = f.api.session(mode === 'status' ? { action: 'create', workspaceId: 'project' } : { action: 'archive', sessionId: 'target' }, f.exec);
    await entered.promise; const rejected = assert.rejects(task, /unloaded/);
    await f.api.dispose(); await rejected;
    reject(new Error('late read rejection')); await Promise.resolve(); assert.deepEqual(f.calls, []);
  }
});
test('unarchive uses only native id, accepts ordinary forks and never activates', async () => {
  const f = fixture();
  for (const sessionId of ['target', 'fork']) assert.deepEqual(await f.api.session({ action: 'unarchive', sessionId }, f.exec),
    { action: 'unarchive', outcome: 'unarchived', sessionId, archived: false });
  assert.deepEqual(f.calls, [['unarchive', 'target'], ['unarchive', 'fork']]);
});
test('creation ambiguity returns bounded unknown, never retries or leaks native message', async () => {
  const f = fixture(); let attempts = 0;
  f.ctx.sessionController.create = async () => { attempts++; throw new Error('private native failure'); };
  const result = await f.api.session({ action: 'create', workspaceId: 'project' }, f.exec);
  assert.equal(result.outcome, 'unknown'); assert.equal(attempts, 1);
  assert.match(result.warning, /never automatically retry/); assert.doesNotMatch(JSON.stringify(result), /private/);
});
test('native attachment failure preserves explicit partial-success identity', async () => {
  const f = fixture();
  f.ctx.sessionController.create = async () => { throw { isDSHRemoteError: true, code: 'session/workspace-attach-failed', details: { sessionId: 'fresh', workspaceId: 'project' } }; };
  const result = await f.api.session({ action: 'create', workspaceId: 'project' }, f.exec);
  assert.equal(result.outcome, 'created-unattached'); assert.equal(result.sessionId, 'fresh'); assert.equal(result.workspaceId, 'project');
  assert.match(result.warning, /do not automatically create/);
});
test('unarchive failure does not claim success or retry', async () => {
  const f = fixture(); let attempts = 0;
  f.ctx.workspaceRegistry.unarchiveSession = async () => { attempts++; throw new Error('private'); };
  const result = await f.api.session({ action: 'unarchive', sessionId: 'target' }, f.exec);
  assert.equal(result.outcome, 'unknown'); assert.equal(attempts, 1); assert.doesNotMatch(JSON.stringify(result), /private/);
});
test('exact caller identity and pre-entry cancellation prevent all mutations', async () => {
  const f = fixture();
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'project' }), { code: 'sender-unavailable' });
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'project' }, { agent: { id: 'caller' } }), { code: 'sender-unavailable' });
  const abort = new AbortController(); abort.abort(new Error('cancelled'));
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'project' }, { ...f.exec, signal: abort.signal }), /cancelled/);
  assert.deepEqual(f.calls, []);
});
test('caller replacement or cancellation during preflight blocks native create', async () => {
  for (const mode of ['replace', 'cancel']) {
    const f = fixture(), pending = deferred(), abort = new AbortController();
    f.workspace.status = () => pending.promise;
    const task = f.api.session({ action: 'create', workspaceId: 'project' }, { ...f.exec, signal: abort.signal });
    if (mode === 'replace') f.agents.set('caller', { id: 'caller' }); else abort.abort(new Error('cancelled'));
    pending.resolve('ok'); await assert.rejects(task); assert.deepEqual(f.calls, []);
  }
});
test('dispose drains admitted native create; late cancellation does not falsify its result', async () => {
  const f = fixture(), entered = deferred(), native = deferred(), abort = new AbortController();
  f.ctx.sessionController.create = () => { entered.resolve(); return native.promise; };
  const task = f.api.session({ action: 'create', workspaceId: 'project' }, { ...f.exec, signal: abort.signal });
  await entered.promise; abort.abort();
  let disposed = false; const disposal = f.api.dispose().then(() => disposed = true);
  await Promise.resolve(); assert.equal(disposed, false);
  native.resolve({ sessionId: 'fresh' }); assert.equal((await task).outcome, 'created'); await disposal;
  await assert.rejects(f.api.session({ action: 'unarchive', sessionId: 'target' }, f.exec), /unloaded/);
});
test('lifecycle recovery guidance never names retired discovery tools', async () => {
  const f = fixture();
  await assert.rejects(f.api.session({ action: 'create', workspaceId: 'missing' }, f.exec), error => {
    assert.match(error.message, /collaboration action list_projects/); assert.doesNotMatch(error.message, /collaboration_list/); return true;
  });
  f.ctx.sessionController.create = async () => { throw new Error('private'); };
  f.ctx.workspaceRegistry.archiveSession = async () => { throw new Error('private'); };
  f.ctx.workspaceRegistry.unarchiveSession = async () => { throw new Error('private'); };
  const results = [await f.api.session({ action: 'create', workspaceId: 'project' }, f.exec)];
  for (const action of ['archive', 'unarchive']) results.push(await f.api.session({ action, sessionId: 'target' }, f.exec));
  for (const result of results) {
    assert.match(result.warning, /collaboration action list_sessions/); assert.doesNotMatch(result.warning, /collaboration_list/);
  }
  f.ctx.sessionController.create = async () => { throw { isDSHRemoteError: true, code: 'session/workspace-attach-failed', details: { workspaceId: 'project', sessionId: 'fresh' } }; };
  const partial = await f.api.session({ action: 'create', workspaceId: 'project' }, f.exec);
  assert.match(partial.warning, /collaboration action list_sessions/); assert.doesNotMatch(partial.warning, /collaboration_list/);
});
test('dispose during cold directory lookup blocks unarchive', async () => {
  const f = fixture(), pending = deferred(); f.ctx.sessionController.list = () => pending.promise;
  const task = f.api.session({ action: 'unarchive', sessionId: 'target' }, f.exec);
  const disposal = f.api.dispose(); pending.resolve({ items: [{ sessionId: 'target' }] });
  await assert.rejects(task, /unloaded/); await disposal; assert.deepEqual(f.calls, []);
});
