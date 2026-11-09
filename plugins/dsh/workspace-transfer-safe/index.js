import { randomUUID } from 'node:crypto';
import { realpath, stat } from 'node:fs/promises';
import { selfTest } from './selftest.js';

export const inject = ['connection', 'tools', 'workspaceRegistry', 'sessionPersistence', 'sessionQuery', 'sessionProjectionCache', 'sessions', 'agents', 'permissionPresets'];
export class TransferError extends Error {
  constructor(code, message, details = {}) { super(message); this.code = code; this.details = details; }
}
const fail = (code, message) => { throw new TransferError(code, message); };
const idValid = id => typeof id === 'string' && id.length > 0 && id.length <= 200 && /^[a-zA-Z0-9_-]+$/.test(id);

// Fail closed rather than repairing, resuming, cancelling, or dropping pending work.
export function validateSource(header, events) {
  if (header.version !== 4) fail('unsupported-format', 'This session format is not supported by this version of the transfer plugin.');
  if (header.isSeeded || header.parentSession || header.origin || header.delegationDepth) fail('seeded-source', 'Seeded and subagent conversations are not supported by this minimal version.');
  if (!events.length) fail('blank-session', 'Start a new conversation in the destination instead.');
  let turn = false, step = false;
  const inbox = { 'next-turn': [], 'next-step': [] };
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.seq !== i || !Number.isFinite(e.time)) fail('invalid-history', 'The source history is not a contiguous current-format log.');
    if (e.type === 'session/end-seed') fail('seeded-source', 'Seeded histories are not supported by this minimal version.');
    if (e.type === 'turn/start') { if (turn) fail('open-turn', 'Finish the source turn before moving.'); turn = true; }
    if (e.type === 'turn/end') { turn = false; step = false; }
    if (e.type === 'step/start') step = true;
    if (e.type === 'step/end') step = false;
    if (e.type === 'agent/inbox/spliced') {
      const d = e.data, list = inbox[d?.target];
      const count = d?.removedCount ?? 0;
      if (!list || !Number.isSafeInteger(d.start) || d.start < 0 || d.start > list.length || !Number.isSafeInteger(count) || count < 0 || count > list.length - d.start || !Array.isArray(d.inserted)) fail('invalid-inbox', 'The pending-message history could not be validated.');
      list.splice(d.start, count, ...d.inserted);
      const ids = [...inbox['next-turn'], ...inbox['next-step']].map(m => m?.id);
      if (ids.some(id => typeof id !== 'string' || !id) || new Set(ids).size !== ids.length) fail('invalid-inbox', 'The pending-message identifiers could not be validated.');
    }
  }
  if (turn || step) fail('open-turn', 'The source has an incomplete turn. Resume and finish it before moving.');
  if (inbox['next-turn'].length || inbox['next-step'].length) fail('pending-inbox', 'The source has queued messages. Consume or cancel them before moving.');
}

export async function moveSession(ctx, sessionId, workspaceId) {
  if (!idValid(sessionId) || !idValid(workspaceId)) fail('invalid-input', 'Choose a conversation and a destination workspace.');
  const registry = ctx.workspaceRegistry;
  const target = registry.get(workspaceId);
  if (!target) fail('workspace-not-found', 'The destination workspace no longer exists.');
  if (registry.archivedSessionIds.includes(sessionId)) fail('already-archived', 'Restore the source conversation before moving it.');
  const ensureClosed = () => {
    if (ctx.agents.get(sessionId) || ctx.sessions.get(sessionId)) fail('source-open', 'Close this conversation before moving it. Idle is not enough.');
  };
  ensureClosed();
  let source;
  try { source = await ctx.sessionPersistence.open(sessionId, 'write'); }
  catch (e) {
    if (e?.code === 'SESSION_ALREADY_OWNED' || e?.name === 'SessionAlreadyOwnedError') fail('source-open', 'Close this conversation before moving it.');
    fail('source-unavailable', 'The source is missing, open, or unavailable. Nothing was moved.');
  }
  let copyId, copied = false, archived = false;
  try {
    ensureClosed();
    const { events } = await source.read();
    const original = source.header;
    validateSource(original, events);
    const targetPath = await realpath(target.path);
    if (!(await stat(targetPath)).isDirectory() || targetPath !== target.path) fail('workspace-missing', 'The destination workspace directory is unavailable or changed.');
    if (await realpath(original.cwd).catch(() => original.cwd) === targetPath) fail('same-workspace', 'The conversation already starts in this workspace.');
    if ((await ctx.waterfall('workspace/session-activity', { sessionId }, async () => [])).length) fail('session-active', 'The source still has running work. Nothing was moved.');
    const preset = ctx.permissionPresets.catalog().defaultOptions.find(x => x.value !== 'auto' && x.value !== 'custom')?.value;
    if (!preset) fail('permissions-unavailable', 'No ordinary permission preset is available. Nothing was moved.');
    copyId = `session-${randomUUID()}`;
    const header = { version: original.version, id: copyId, createdAt: Date.now(), cwd: targetPath, isSeeded: true,
      ...(original.agentPreset === undefined ? {} : { agentPreset: original.agentPreset }) };
    // A balanced non-seeded source needs no synthetic tool/turn repair. The
    // inherited prefix remains byte-for-byte equivalent; overrides are new facts.
    const seed = [...events];
    const append = (type, data) => seed.push({seq: seed.length, time: Math.max(Date.now(), events.at(-1).time), type, data});
    append('session/end-seed', { inherited: true });
    append('working-directory/change', { cwd: targetPath });
    append('permission/preset', { preset });
    append('sandbox/mode', { mode: 'read-only' });
    append('approval/policy', { policy: 'ask' });
    const writer = await ctx.sessionPersistence.create(header, { inheritedEventCount: events.length });
    try {
      await writer.append(seed);
      await writer.flush();
      const stored = await writer.read();
      if (JSON.stringify(stored.events) !== JSON.stringify(seed)) fail('readback-failed', 'The new log failed verification. The original remains unarchived.');
    } finally { await writer.close(); }
    // Query validates replay through the native reader without creating an Agent.
    const replay = await ctx.sessionQuery.readSession(copyId);
    if (replay.session.cwd !== targetPath || replay.events.length !== seed.length) fail('replay-failed', 'The new history failed native validation. The original remains unarchived.');
    const projections = ctx.sessionProjectionCache.coldSnapshot(header, events.length, seed);
    if (projections.values.workingDirectory !== targetPath || !projections.values.permissions?.currentValue || projections.values.permissions.currentValue === 'auto' || replay.events.findLast(e => e.type === 'sandbox/mode')?.data.mode !== 'read-only' || replay.events.findLast(e => e.type === 'approval/policy')?.data.policy !== 'ask') fail('permissions-unverified', 'The copy permissions could not be verified. The original remains unarchived.');
    await target.attachSession(copyId);
    copied = true;
    ctx.emit('api-session/added', {sessionId:copyId, updatedAt:header.createdAt, agentAvailable:false, formatStatus:'current', running:false, blank:false, cwd:targetPath,
      projections:{kind:'cached',asOfSeq:projections.asOfSeq,values:projections.values}});
    // Rechecks activity natively, and archives only after a durable verified copy.
    await registry.archiveSession(sessionId);
    archived = true;
    return {ok:true,sessionId:copyId,workspaceId,copied:true,sourceArchived:true};
  } catch (e) {
    if (copyId) throw new TransferError('partial-transfer', archived ? 'The transfer completed but cleanup needs attention. Do not repeat it.' : 'The original was not archived. A partial copy may exist; do not repeat the transfer blindly.', {copySessionId:copyId,attached:copied,sourceArchived:archived});
    throw e;
  } finally {
    try { await source.close(); }
    catch {
      throw new TransferError('source-close-failed', 'The source lock could not be released cleanly. Do not repeat the transfer; restart Harness first.', { ...(copyId ? {copySessionId:copyId} : {}), sourceArchived:archived, attached:copied });
    }
  }
}

function publicError(e) {
  return {ok:false,error:e instanceof TransferError ? {code:e.code,message:e.message,...e.details} : {code:'transfer-failed',message:'The operation failed. The original history was not deleted. Check the workspace and close the source before retrying.'}};
}
export function apply(ctx) {
  let serial = Promise.resolve(), closing = false;
  const run = fn => {
    if (closing) return Promise.reject(new TransferError('closing', 'The plugin is stopping.'));
    const result = serial.then(fn); serial = result.catch(() => {}); return result;
  };
  const workspaces = () => ctx.workspaceRegistry.list().map(w => ({workspaceId:w.id,title:w.title,path:w.path}));
  const operation = args => run(async () => {
    try {
      if (args.action === 'list') return {ok:true,workspaces:workspaces()};
      if (args.action === 'move') return await moveSession(ctx,args.sessionId,args.workspaceId);
      if (args.action === 'self_test') {
        try { return await selfTest(ctx,moveSession); }
        catch (e) { return {ok:false,error:{code:'self-test-failed',message:'The disposable native test failed. Fixture logs and directories are retained.',...(e?.details ?? {})}}; }
      }
      fail('invalid-input', 'Unsupported action.');
    } catch(e) { return publicError(e); }
  });
  ctx.effect(() => ctx.connection.fetch.register({path:'/api/mainframe/workspace-transfer',methods:['POST'],requestBody:'buffered',fetch:async request => {
    const admission = ctx.connection.admit(request);
    if ('rejection' in admission || admission.peer !== ctx.connection.browserPeer || request.headers.get('x-mainframe-workspace-transfer') !== '1' || !request.headers.get('content-type')?.startsWith('application/json')) return new Response(null,{status:403});
    const headers = {'content-type':'application/json','cache-control':'no-store','x-content-type-options':'nosniff'};
    try {
      const text = await request.text();
      if (text.length > 4096) return new Response(null,{status:413});
      const args = JSON.parse(text);
      if (!args || Object.keys(args).some(k => !['sessionId','workspaceId'].includes(k))) return new Response(null,{status:400});
      return new Response(JSON.stringify(await operation({...args,action:'move'})),{headers});
    } catch { return new Response(JSON.stringify(publicError(null)),{headers,status:400}); }
  }}));
  ctx.effect(() => ctx.tools.register({name:'workspace_transfer',description:'List destination workspaces or move a CLOSED conversation by making a new seeded session and archiving the original last. Only on explicit user request; never move the current/live chat. No deletion, project-file copy, schedule migration, or model execution. Resets copied permissions to read-only with approval prompts. Seeded/subagent/incomplete/queued histories are refused. self_test touches only newly generated disposable fixtures.',parameters:{type:'object',properties:{action:{type:'string',enum:['list','move','self_test']},sessionId:{type:'string',description:'Source session ID for move; must be closed.'},workspaceId:{type:'string',description:'Existing destination workspace ID from list.'}},required:['action'],additionalProperties:false},output:{schema:{},render:(_args,value)=>[{type:'text',text:JSON.stringify(value)}]},execute:operation}));
  ctx.on('dispose', () => { closing = true; return serial; });
}
