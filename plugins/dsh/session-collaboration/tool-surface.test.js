import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { collaborationSchema, createCollaborationTool, validateCollaboration } from './tool-surface.js';
import { createCollaboration } from './core.js';

function fixture() {
  const calls = [];
  const record = name => async (args, exec) => { calls.push({ name, args, exec }); return { name, args }; };
  const tool = createCollaborationTool({ list: record('list'), read: record('read'), send: record('send'), tasks: record('tasks') },
    { waitMany: record('waitMany') }, { session: record('session'), models: record('models') });
  return { tool, calls };
}
const examples = [
  [{ action: 'list_projects' }, 'list', { kind: 'projects' }],
  [{ action: 'list_sessions', workspaceId: 'project', includeArchived: true }, 'list', { kind: 'sessions', workspaceId: 'project', includeArchived: true }],
  [{ action: 'read', sessionId: 'cold', throughSeq: -1 }, 'read', { sessionId: 'cold', throughSeq: -1 }],
  [{ action: 'send', sessionId: 'cold', message: 'Review this task', notify: false, mode: 'steer' }, 'send', { sessionId: 'cold', message: 'Review this task', notify: false, mode: 'steer' }],
  [{ action: 'wait', targets: [{ sessionId: 'cold', afterSeq: 42 }] }, 'waitMany', { targets: [{ sessionId: 'cold', afterSeq: 42 }] }],
  [{ action: 'wait', targets: [{ sessionId: 'cold' }, { sessionId: 'other' }], mode: 'any' }, 'waitMany', { targets: [{ sessionId: 'cold' }, { sessionId: 'other' }], mode: 'any' }],
  [{ action: 'list_tasks', group: 'review', limit: 64 }, 'tasks', { action: 'list', group: 'review', limit: 64 }],
  [{ action: 'get_task', taskId: 'task' }, 'tasks', { action: 'get', taskId: 'task' }],
  [{ action: 'cancel_task', taskId: 'task' }, 'tasks', { action: 'cancel', taskId: 'task' }],
  [{ action: 'models' }, 'models', {}],
  [{ action: 'models', provider: 'provider' }, 'models', { provider: 'provider' }],
  [{ action: 'models', provider: 'provider', model: 'model' }, 'models', { provider: 'provider', model: 'model' }],
  ...[
    { action: 'create', workspaceId: 'project' },
    { action: 'create', workspaceId: 'project', title: 'Review installation' },
    { action: 'create', workspaceId: 'project', provider: 'p', model: 'm', reasoning_effort: 'high' },
    { action: 'archive', sessionId: 'cold' }, { action: 'unarchive', sessionId: 'cold' },
    { action: 'get_model', sessionId: 'cold' }, { action: 'set_model', sessionId: 'cold', provider: 'p', model: 'm' },
  ].map(args => [args, 'session', args]),
];

test('all actions dispatch once through existing owners with exact context and fields', async () => {
  const { tool, calls } = fixture(), exec = { agent: { id: 'caller' }, signal: new AbortController().signal };
  for (const [args, name, expected] of examples) {
    const count = calls.length;
    assert.deepEqual(await tool.execute(args, exec), { name, args: expected });
    assert.equal(calls.length, count + 1);
    assert.deepEqual(calls.at(-1), { name, args: expected, exec });
  }
  assert.deepEqual([...new Set(examples.map(([args]) => args.action))], collaborationSchema.parameters.properties.action.enum);
});

test('invalid and action-incompatible inputs fail before any owner call', async () => {
  const { tool, calls } = fixture();
  const invalid = [undefined, null, [], {}, { action: 'help' }, { action: 'constructor' },
    { action: 'send', sessionId: 'cold', message: 'x', unknown: 1 },
    { action: 'send', sessionId: 'cold', message: 'x', provider: 'p', model: 'm' },
    { action: 'create', workspaceId: 'project', sessionId: 'cold' },
    { action: 'archive', sessionId: 'cold', mode: 'steer' },
    { action: 'create', workspaceId: 'project', title: 'x'.repeat(201) },
    { action: 'create', workspaceId: 'project', title: null },
    ...['read', 'archive', 'unarchive', 'get_model', 'set_model'].map(action => ({ action, sessionId: 'cold', title: 'Name' })),
    { action: 'set_model', sessionId: 'cold', provider: 'p', model: 'm', message: 'x' },
    { action: 'cancel_task', taskId: 'task', group: 'review' },
    { action: 'get_model', sessionId: 'cold', provider: 'p', model: 'm' },
    { action: 'send', sessionId: 'cold', message: 'x', mode: 'any' },
    { action: 'send', sessionId: 'cold', message: 'x', notify: 'false' },
    { action: 'send', sessionId: 'cold', message: ' ' },
    { action: 'send', sessionId: 'cold', message: 'x'.repeat(16001) },
    { action: 'send', sessionId: 'cold', message: 'x', label: 'x'.repeat(121) },
    { action: 'send', sessionId: 'cold', message: 'x', notifyTimeoutMs: 999 },
    { action: 'send', sessionId: 'cold', message: 'x', notifyTimeoutMs: 3600001 },
    { action: 'wait', sessionId: 'cold' }, { action: 'wait', targets: [] },
    { action: 'wait', targets: Array.from({ length: 9 }, (_, i) => ({ sessionId: `s${i}` })) },
    { action: 'wait', targets: [{ sessionId: 'cold' }, { sessionId: 'cold' }] },
    { action: 'wait', targets: [{ sessionId: 'cold', unknown: true }] },
    { action: 'wait', targets: [{ sessionId: 'cold', afterSeq: -2 }] },
    { action: 'wait', targets: [{ sessionId: 'cold' }], mode: 'followup' },
    { action: 'wait', targets: [{ sessionId: 'cold' }], timeoutMs: 0 },
    { action: 'wait', targets: [{ sessionId: 'cold' }], timeoutMs: 120001 },
    { action: 'models', model: 'm' }, { action: 'create', workspaceId: 'project', provider: 'p' },
    { action: 'create', workspaceId: 'project', reasoning_effort: 'high' },
    { action: 'list_projects', workspaceId: 'project' }, { action: 'list_tasks', limit: 65 },
    { action: 'list_sessions', includeArchived: null }, { action: 'read', sessionId: 'title with spaces' },
    { action: 'read', sessionId: 'cold', maxMessages: 51 }, { action: 'read', sessionId: 'cold', maxChars: 99 },
    { action: 'read', sessionId: 'cold', beforeSeq: -1 }, { action: 'read', sessionId: 'cold', throughSeq: 1.2 },
    { action: 'read', sessionId: 'cold', includeGoal: undefined },
    { action: 'list_projects', offset: Number.MAX_SAFE_INTEGER + 1 },
    ...examples.flatMap(([args]) => ['sessionId', 'workspaceId', 'message', 'targets', 'taskId'].filter(key => key in args).map(key => { const copy = { ...args }; delete copy[key]; return copy; })).filter(args => args.action !== 'list_sessions'),
  ];
  for (const args of invalid) {
    await assert.rejects(tool.execute(args, {}), error => error.code === 'invalid-input', JSON.stringify(args));
    assert.equal(calls.length, 0);
  }
});

test('every action rejects every unrelated schema field before dispatch', async () => {
  const allowed = {
    list_projects: ['includeArchived', 'offset', 'limit'], list_sessions: ['workspaceId', 'includeArchived', 'offset', 'limit'],
    read: ['sessionId', 'maxMessages', 'maxChars', 'beforeSeq', 'throughSeq', 'includeGoal', 'includeTools'],
    send: ['sessionId', 'message', 'mode', 'notify', 'notifyTimeoutMs', 'label', 'group'], wait: ['targets', 'mode', 'timeoutMs'],
    list_tasks: ['group', 'offset', 'limit'], get_task: ['taskId'], cancel_task: ['taskId'], models: ['provider', 'model', 'offset', 'limit'],
    create: ['workspaceId', 'title', 'provider', 'model', 'reasoning_effort'], archive: ['sessionId'], unarchive: ['sessionId'], get_model: ['sessionId'],
    set_model: ['sessionId', 'provider', 'model', 'reasoning_effort'],
  };
  const values = { title: 'Name', workspaceId: 'p', sessionId: 's', includeArchived: false, offset: 0, limit: 1, maxMessages: 1, maxChars: 100, beforeSeq: 0, throughSeq: -1, includeGoal: true, includeTools: false, message: 'x', mode: 'all', notify: true, notifyTimeoutMs: 1000, label: 'l', group: 'g', targets: [{ sessionId: 's' }], timeoutMs: 1, taskId: 't', provider: 'p', model: 'm', reasoning_effort: 'high' };
  for (const [args] of examples) for (const [key, value] of Object.entries(values)) {
    if (allowed[args.action].includes(key)) continue;
    const { tool, calls } = fixture();
    await assert.rejects(tool.execute({ ...args, [key]: value }, {}), { code: 'invalid-input' });
    assert.equal(calls.length, 0);
  }
});

test('flat closed JSON Schema stays portable, bounded and English-only', () => {
  const schema = collaborationSchema.parameters;
  assert.equal(schema.type, 'object'); assert.equal(schema.additionalProperties, false);
  assert.deepEqual(schema.required, ['action']); assert.equal(schema.oneOf, undefined);
  assert.equal(schema.properties.targets.items.additionalProperties, false);
  assert.deepEqual(schema.properties.targets.items.required, ['sessionId']);
  const serialized = JSON.stringify([collaborationSchema]);
  assert.ok(serialized.length < 5000, `schema chars: ${serialized.length}`);
  assert.doesNotMatch(serialized, /[\u0400-\u04ff]/);
  assert.doesNotMatch(serialized, /collaboration_(list|send|wait|session)/);
  assert.match(serialized, /never auto-retry/); assert.match(serialized, /not human authority/);
  assert.match(serialized, /notify/);
  assert.match(serialized, /archive refuses observed activity; sends no stop\/delete request/);
  assert.match(serialized, /Native idle check is not atomic: racing input may be consumed/);
  assert.doesNotMatch(serialized, /never forces\/stops\/deletes/);
  assert.equal(schema.properties.afterSeq, undefined); assert.equal(schema.properties.targets.type, 'array');
  for (const [args] of examples) assert.doesNotThrow(() => validateCollaboration(JSON.parse(JSON.stringify(args))));
});

test('public cold discovery uses directory APIs only; invalid send cannot load a target', async () => {
  const calls = [];
  const ctx = {
    workspaceRegistry: { list: () => [{ id: 'project', title: 'Project', path: '/project', sessionIds: ['cold', 'archived'] }], archivedSessionIds: ['archived'] },
    sessionController: { list: async () => { calls.push('list'); return { items: [{ sessionId: 'cold' }, { sessionId: 'archived' }] }; }, resolveAgent: () => { throw new Error('must not load'); } },
    agents: { get: () => undefined },
  };
  const api = createCollaboration(ctx, () => { throw new Error('must not create a message'); });
  await api.ready;
  const tool = createCollaborationTool(api, {}, {});
  try {
    const result = await tool.execute({ action: 'list_sessions', workspaceId: 'project', includeArchived: true }, {});
    assert.deepEqual(result.items.map(row => [row.sessionId, row.status, row.archived]), [['cold', 'unloaded', false], ['archived', 'unloaded', true]]);
    await assert.rejects(tool.execute({ action: 'send', sessionId: 'cold', message: 'task', provider: 'p' }, {}), { code: 'invalid-input' });
    assert.deepEqual(calls, ['list']);
  } finally { await api.dispose(); }
});

test('plugin retains public service dependencies without private hooks or legacy registrations', async () => {
  const source = await readFile(new URL('./index.js', import.meta.url), 'utf8');
  assert.match(source, /export const inject = \['tools', 'workspaceRegistry', 'sessionController', 'agents', 'storageDomain', 'llm', 'sessionTitle'\]/);
  assert.equal((source.match(/ctx\.tools\.register\(/g) ?? []).length, 1);
  assert.match(source, /ctx\.effect\(\(\)=>ctx\.tools\.register\(createCollaborationTool/);
  assert.doesNotMatch(source, /collaboration_(list|read|send|wait|tasks|models|session)|defineProperty|\.internal\b/);
});
