import { CollaborationError, identifier } from './core.js';
import { createModelSelection, requestedSelection } from './model-selection.js';
import { readBeforeAdmission } from './lifecycle-reads.js';

const fail = (code, message) => { throw new CollaborationError(code, message); };
const UNKNOWN = 'The native operation may have committed. Inspect collaboration action list_sessions before deciding what to do; never automatically retry creation.';
const ARCHIVE_NOTE = 'No stop request is sent. Native snapshot is not an atomic lock; a racing turn/input can be blocked or consumed before commitment. Already-archived targets skip the native inactivity check.';
const ACTIVITY_KINDS = new Set(['turn', 'job', 'subagent', 'schedule']);
const busyArchive = (sessionId, activityKinds) => ({ action: 'archive', outcome: 'busy', sessionId,
  activityKinds: [...new Set(activityKinds)],
  note: 'This operation did not archive the session or request stopping. Finish active work explicitly before retrying.' });

// Mutations are native-owned and cannot be cancelled once entered. Track the
// actual promise through disposal instead of abandoning it on tool cancellation.
export function createLifecycleManagement(ctx, { normalizeTitle } = {}) {
  const lifetime = new AbortController(), operations = new Set(), modelApi = createModelSelection(ctx);
  function track(task) {
    operations.add(task);
    task.then(() => operations.delete(task), () => operations.delete(task));
    return task;
  }
  const session = (args = {}, exec = {}) => track(run(args, exec));
  const models = (args = {}, exec = {}) => track((async () => {
    const signal = exec.signal ? AbortSignal.any([lifetime.signal, exec.signal]) : lifetime.signal;
    caller(exec, signal);
    return modelApi.models(args, signal);
  })());
  function caller(exec, signal) {
    signal.throwIfAborted();
    const agent = exec.agent;
    if (!agent || ctx.agents.get(agent.id) !== agent)
      fail('sender-unavailable', 'Lifecycle management requires the exact live calling Agent.');
    return agent;
  }
  function selectTarget(target, sessionId, selection) {
    if (!target || target.id !== sessionId || ctx.agents.get(sessionId) !== target ||
        target.session?.header?.origin === 'subagent' || ctx.workspaceRegistry.archivedSessionIds.includes(sessionId))
      fail('target-unavailable', 'Target was replaced or archived before selection.');
    // Public Agent API only. Native GUI image-admission serialization is private.
    // No await separates the final live/archive checks from selection admission.
    return target.model.select(selection);
  }
  async function run(args, exec) {
    const signal = exec.signal ? AbortSignal.any([lifetime.signal, exec.signal]) : lifetime.signal;
    const sender = caller(exec, signal);
    if (!args || typeof args !== 'object' || Array.isArray(args) ||
        Object.keys(args).some(key => !['action', 'workspaceId', 'sessionId', 'title', 'provider', 'model', 'reasoning_effort'].includes(key)))
      fail('invalid-input', 'Unsupported session parameter.');
    const { action } = args;
    if (!['create', 'archive', 'unarchive', 'get_model', 'set_model'].includes(action))
      fail('invalid-input', 'Unknown session action.');
    const selection = requestedSelection(args, action === 'set_model');
    if (selection && !['create', 'set_model'].includes(action))
      fail('invalid-input', 'Model selection is accepted only by create or set_model.');
    if (args.title !== undefined && action !== 'create') fail('invalid-input', 'Only create accepts title.');
    if (action === 'create') {
      if (args.sessionId !== undefined) fail('invalid-input', 'create does not accept sessionId; no session reuse.');
      if (args.title !== undefined) {
        if (typeof args.title !== 'string' || !args.title.trim() || [...args.title].length > 200)
          fail('invalid-input', 'title must contain visible text, at most 200 characters.');
        if (typeof ctx.sessionTitle?.rename !== 'function' || typeof normalizeTitle !== 'function')
          fail('title-unavailable', 'Native session title support is unavailable; no session was created.');
        if (!normalizeTitle(args.title, Number.MAX_SAFE_INTEGER))
          fail('invalid-input', 'title must contain visible text.');
      }
      const workspaceId = identifier(args.workspaceId);
      const workspace = ctx.workspaceRegistry.get(workspaceId);
      if (!workspace) fail('workspace-not-found', 'Select an existing project from collaboration action list_projects.');
      if (await readBeforeAdmission(() => workspace.status(), signal) !== 'ok') fail('workspace-unavailable', 'The existing project directory is unavailable.');
      if (selection) await modelApi.validate(selection, signal);
      caller(exec, signal);
      if (ctx.workspaceRegistry.get(workspaceId) !== workspace)
        fail('workspace-unavailable', 'The project registration changed before creation.');
      try {
        // Omit sessionId, cwd, preset and all ancestry: native fresh identity,
        // configured default preset, no prompt/send/model run or goal rearming.
        const result = await ctx.sessionController.create({ workspaceId });
        const created = { action, outcome: 'created', workspaceId, sessionId: result.sessionId,
          ...(result.agentPreset === undefined ? {} : { agentPreset: result.agentPreset }) };
        if (!selection && args.title === undefined) return created;
        // Once creation is admitted, retain its identity and drain native calls.
        // Tool cancellation cannot abandon it; disposal prevents new mutations.
        // Title/model results are independent: neither catch loses a known ID.
        let target, modelUnknown = !!selection;
        if (args.title !== undefined) created.titleStatus = 'unknown';
        try {
          lifetime.signal.throwIfAborted();
          const resolved = await ctx.sessionController.resolveAgent(result.sessionId);
          if ('error' in resolved) throw resolved.error;
          target = resolved.agent;
        } catch { /* Configuration unavailable; preserve identity below. */ }
        if (target && args.title !== undefined) {
          try {
            lifetime.signal.throwIfAborted();
            if (target.id !== result.sessionId || ctx.agents.get(result.sessionId) !== target ||
                target.session?.id !== result.sessionId || target.session.header?.origin === 'subagent' ||
                ctx.workspaceRegistry.archivedSessionIds.includes(result.sessionId)) throw new Error('Unexpected target');
            // Native metadata only: no user/message, prompt, or title LLM call.
            const accepted = ctx.sessionTitle.rename(target.session, args.title);
            created.title = accepted.title;
            created.titleStatus = 'applied';
          } catch { /* rename may append before throwing: do not retry. */ }
        }
        if (target && selection) {
          try {
            await modelApi.validate(selection, lifetime.signal);
            lifetime.signal.throwIfAborted();
            await selectTarget(target, result.sessionId, selection);
            Object.assign(created, { selection, appliedFrom: 'next-unprepared-step', defaultChanged: false });
            modelUnknown = false;
          } catch { /* Keep accepted title even if model selection is uncertain. */ }
        }
        const titleUnknown = created.titleStatus === 'unknown';
        if (titleUnknown || modelUnknown) {
          created.outcome = titleUnknown ? modelUnknown ? 'created-configuration-unknown' : 'created-title-unknown' : 'created-model-unknown';
          created.warning = 'Session exists; requested configuration may not have committed. ' +
            (titleUnknown ? 'Inspect its title with list_sessions or the GUI. ' : '') +
            (modelUnknown ? 'Use get_model and, if needed, set_model on this ID. ' : '') +
            'Never recreate or delete it automatically.';
        }
        return created;
      } catch (error) {
        // Native attachment errors explicitly identify an already-created session.
        if (error?.isDSHRemoteError === true && error.code === 'session/workspace-attach-failed' &&
            error.details?.workspaceId === workspaceId &&
            typeof error.details?.sessionId === 'string' && /^[\w-]{1,200}$/.test(error.details.sessionId))
          return { action, outcome: 'created-unattached', workspaceId, sessionId: error.details.sessionId,
            warning: 'Session created, but project attachment failed. Inspect collaboration action list_sessions; do not automatically create another session.' };
        // Other exceptions can also follow creation. Never replay or delete.
        return { action, outcome: 'unknown', workspaceId, warning: UNKNOWN };
      }
    }
    if (args.workspaceId !== undefined) fail('invalid-input', 'Only create accepts workspaceId.');
    const sessionId = identifier(args.sessionId);
    if (sessionId === sender.id) fail('self-target', 'Lifecycle actions require another ordinary session.');
    const { items } = await readBeforeAdmission(() => ctx.sessionController.list({}, signal), signal);
    caller(exec, signal);
    const row = items.find(item => item.sessionId === sessionId);
    if (!row) fail('session-not-found', 'Session not found in the ordinary session directory.');
    if (row.origin === 'subagent' || ctx.agents.get(sessionId)?.session?.header?.origin === 'subagent')
      fail('subagent-target', 'Lifecycle management excludes subagent sessions.');
    if (action === 'get_model') {
      const target = ctx.agents.get(sessionId);
      const current = target?.model.current();
      return { action, sessionId, outcome: current ? 'known' : 'unknown', loaded: !!target,
        ...(current ? { selection: current } : {}),
        semantics: 'Session choice, not necessarily the running prepared step; unloaded sessions are not resumed.' };
    }
    if (action === 'set_model') {
      if (ctx.workspaceRegistry.archivedSessionIds.includes(sessionId)) fail('archived-target', 'Unarchive the target explicitly before changing its model.');
      await modelApi.validate(selection, signal);
      caller(exec, signal);
      if (ctx.workspaceRegistry.archivedSessionIds.includes(sessionId)) fail('archived-target', 'Target was archived during model validation; no Agent was loaded.');
      // Resolve may load the ordinary Agent but never sends input or runs a step.
      // From here the native operation is admitted and drained, not abandoned.
      try {
        const resolved = await ctx.sessionController.resolveAgent(sessionId);
        if ('error' in resolved) throw resolved.error;
        const target = resolved.agent;
        if (target.id !== sessionId || target.session?.header?.origin === 'subagent') throw new Error('Unexpected target');
        await modelApi.validate(selection, lifetime.signal);
        await selectTarget(target, sessionId, selection);
        return { action, outcome: 'selected', sessionId, selection, appliedFrom: 'next-unprepared-step', defaultChanged: false };
      } catch {
        return { action, outcome: 'unknown', sessionId,
          warning: 'Selection may have committed. Use get_model before deciding whether to retry; no global default was changed.' };
      }
    }
    if (action === 'archive') {
      const alreadyArchived = ctx.workspaceRegistry.archivedSessionIds.includes(sessionId);
      if (!alreadyArchived) {
        const before = ctx.agents.get(sessionId);
        let state;
        try { state = await readBeforeAdmission(() => ctx.sessionController.state({ sessionId }, signal), signal); }
        catch {
          caller(exec, signal);
          fail('target-unavailable', 'Passive activity state is unavailable; no archive was requested.');
        }
        caller(exec, signal);
        const target = ctx.agents.get(sessionId);
        if (target !== before || target?.session?.header?.origin === 'subagent')
          fail('target-unavailable', 'Target changed during archive preflight; no archive was requested.');
        if (!state || typeof state.running !== 'boolean' || !Array.isArray(state.pendingInput) ||
            (state.queue !== null && !Array.isArray(state.queue)))
          fail('target-unavailable', 'Passive activity state is incomplete; no archive was requested.');
        const activity = [];
        if (state.running || (target && target.status !== 'idle')) activity.push('turn');
        if (state.queue?.length || target?.inbox?.hasPending) activity.push('queued-input');
        if (state.pendingInput.length) activity.push('pending-input');
        if (activity.length) return busyArchive(sessionId, activity);
        // Cold state deliberately has queue:null; it cannot prove a durable inbox
        // empty. These passive/live checks reduce races, never provide a lock.
      }
      caller(exec, signal);
      try {
        // No options: native rejects turn/job/subagent/schedule activity. Its
        // asynchronous write still races new work; do not stop, clear or rollback.
        await ctx.workspaceRegistry.archiveSession(sessionId);
        return { action, outcome: alreadyArchived ? 'already-archived' : 'archived', sessionId, archived: true,
          archiveSafety: alreadyArchived ? 'already-archived-no-check' : 'native-inactivity-snapshot', note: ARCHIVE_NOTE };
      } catch (error) {
        if (error?.name === 'WorkspaceActiveSessionError' && error.sessionId === sessionId && Array.isArray(error.activity))
          return busyArchive(sessionId, error.activity.slice(0, 100).map(item => ACTIVITY_KINDS.has(item?.kind) ? item.kind : 'other'));
        if (error?.name === 'WorkspaceUnknownSessionError' && error.sessionId === sessionId)
          fail('session-not-found', 'Target disappeared before native archive admission; no archive was written by this operation.');
        return { action, outcome: 'unknown', sessionId,
          warning: 'Archival may have committed. Inspect collaboration action list_sessions with includeArchived:true; do not automatically retry or unarchive.',
          note: ARCHIVE_NOTE };
      }
    }
    try {
      await ctx.workspaceRegistry.unarchiveSession(sessionId);
      return { action, outcome: 'unarchived', sessionId, archived: false };
    } catch {
      return { action, outcome: 'unknown', sessionId,
        warning: 'Unarchival may have committed. Inspect collaboration action list_sessions with includeArchived:true before deciding what to do.' };
    }
  }
  async function dispose() {
    lifetime.abort(new Error('Session collaboration lifecycle unloaded'));
    await Promise.allSettled([...operations]);
  }
  return { session, models, dispose };
}
