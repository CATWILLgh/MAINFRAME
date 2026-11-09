import { createTaskStore, memoryTaskTable, taskLabel } from './tasks.js';

export class CollaborationError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}
const fail = (code, message) => { throw new CollaborationError(code, message); };
export function integer(value, fallback, min, max, name) {
  const n = value ?? fallback;
  if (!Number.isSafeInteger(n) || n < min || n > max) fail('invalid-input', `${name} must be an integer from ${min} to ${max}.`);
  return n;
}
export function identifier(value) {
  if (typeof value !== 'string' || !/^[\w-]{1,200}$/.test(value)) fail('invalid-input', 'A valid session or workspace ID is required.');
  return value;
}
const clip = (text, limit = 1000) => typeof text === 'string' ? text.slice(0, limit) : undefined;
export function stateView(state) {
  return { cursor: state.cursor, active: state.active, running: state.running,
    queued: state.queue?.length ?? null, pendingInput: Array.isArray(state.pendingInput)
      ? [...new Set(state.pendingInput.filter(kind=>['approval','question','other'].includes(kind)))].slice(0,3) : [] };
}
function goalView(goal) {
  if (!goal) return null;
  return { id: goal.id, revision: goal.revision, phase: goal.phase, objective: clip(goal.objective, 8000),
    objectiveTruncated: typeof goal.objective === 'string' && goal.objective.length > 8000,
    maxGoalRounds: goal.maxGoalRounds, roundsStarted: goal.roundsStarted,
    activation: goal.activation, blockedReason: goal.blockedReason ? {code: clip(goal.blockedReason.code), message:clip(goal.blockedReason.message,2000)} : undefined };
}
// Wire records are {type:'event', event}. Only append-message text is exposed;
// no thought blocks, attachments, or arbitrary event payloads escape this boundary.
export function historyView(records, { maxChars = 12000, includeTools = false, newestFirst = false } = {}) {
  const output = []; let remaining = maxChars, truncated = false, nextBeforeSeq;
  const ordered = newestFirst ? records : [...records].reverse();
  for (const { event } of ordered) {
    if (!event) continue;
    if (remaining <= 0 || output.length >= 100) { truncated = true; break; }
    nextBeforeSeq = event.seq;
    if (!['user/message', 'assistant/message', 'turn/end', 'tool/result'].includes(event.type)) continue;
    if (event.type === 'tool/result') {
      if (!includeTools || event.surfaceOp!=='append') continue;
      const marker=`[tool-result: ${clip(event.data?.message?.toolCallId,200)??'unnamed'}; payload omitted]`;
      const text=marker.slice(0,remaining);remaining-=text.length;
      const textTruncated=text.length<marker.length;truncated ||= textTruncated;
      output.push({seq:event.seq,type:event.type,text,textTruncated});continue;
    }
    if (event.type === 'turn/end') {
      output.push({ seq:event.seq, type:event.type, reason:clip(event.data?.reason?.kind,100) });
      continue;
    }
    if(event.surfaceOp!=='append') continue;
    const message=event.type==='user/message'?event.data:event.data?.message;
    const parts = []; let textTruncated = false;
    for (const part of message?.content ?? []) {
      let text;
      if (part.type === 'text') text = part.text;
      else if (includeTools && part.type === 'tool-call') text = `[${part.type}: ${clip(part.name ?? part.id, 200) ?? 'unnamed'}; payload omitted]`;
      if (typeof text !== 'string' || text.length === 0) continue;
      if (parts.length > 0) { parts.push('\n'); remaining--; }
      const slice = text.slice(0, remaining);
      parts.push(slice); remaining -= slice.length;
      if (slice.length < text.length) { textTruncated = true; truncated = true; }
      if (remaining === 0) { textTruncated = true; truncated = true; break; }
    }
    output.push({seq:event.seq, type:event.type, messageId:clip(message?.id,200), source:clip(message?.source?.kind,100), text:parts.join(''), textTruncated});
  }
  if (!newestFirst) output.reverse();
  return {records:output, truncated, nextBeforeSeq};
}
export function createCollaboration(ctx, createUserMessage, options = {}) {
  const lifetime = new AbortController();
  const watches = new Map(), dispatches = new Set(), admitted = new Map(), operations = new Set();
  const tracked=fn=>(...args)=>{const task=fn(...args);operations.add(task);task.then(()=>operations.delete(task),()=>operations.delete(task));return task;};
  const store = createTaskStore(options.table ?? memoryTaskTable(), options);
  const now = options.now ?? Date.now;
  let ready;
  const launch = operation => { const task=operation().catch(()=>{}).finally(()=>dispatches.delete(task));dispatches.add(task);return task; };
  const signalFor = signal => signal ? AbortSignal.any([lifetime.signal, signal]) : lifetime.signal;
  function abortable(operation,signal) {
    signal.throwIfAborted();
    return new Promise((resolve,reject)=>{
      const abort=()=>{signal.removeEventListener('abort',abort);reject(signal.reason);};
      signal.addEventListener('abort',abort,{once:true});
      Promise.resolve().then(()=>{signal.throwIfAborted();return operation();}).then(value=>{signal.removeEventListener('abort',abort);resolve(value);},error=>{signal.removeEventListener('abort',abort);reject(error);});
    });
  }
  const archived = id => ctx.workspaceRegistry.archivedSessionIds.includes(id);
  const ensureSender = exec => {
    const sender = exec?.agent;
    if (!sender || ctx.agents.get(sender.id) !== sender) fail('sender-unavailable', 'Send requires the exact live calling Agent.');
    return sender;
  };
  const liveStatus = id => ctx.agents.get(id)?.status ?? 'unloaded';
  async function list(args = {}, exec = {}) {
    const signal = signalFor(exec.signal); signal.throwIfAborted();
    const offset = integer(args.offset,0,0,1000000,'offset'), limit = integer(args.limit,30,1,100,'limit');
    const projects = ctx.workspaceRegistry.list();
    if ((args.kind ?? 'projects') === 'projects') {
      const rows = projects.map(w => ({workspaceId:w.id,title:clip(w.title,300),path:clip(w.path,2000),sessionCount:w.sessionIds.filter(id => args.includeArchived || !archived(id)).length}));
      return {kind:'projects',items:rows.slice(offset,offset+limit),nextOffset:offset+limit<rows.length?offset+limit:null,total:rows.length};
    }
    if (args.kind !== 'sessions') fail('invalid-input','kind must be projects or sessions.');
    const workspace = args.workspaceId === undefined ? undefined : projects.find(w=>w.id===identifier(args.workspaceId));
    if (args.workspaceId !== undefined && !workspace) fail('workspace-not-found','Workspace not found.');
    const memberships = new Map(projects.flatMap(w=>w.sessionIds.map(id=>[id,w.id])));
    const {items} = await ctx.sessionController.list({},signal);
    const rows = items.filter(row => row.origin !== 'subagent' && (!workspace || workspace.sessionIds.includes(row.sessionId)) && (args.includeArchived || !archived(row.sessionId)));
    return {kind:'sessions',items:rows.slice(offset,offset+limit).map(row=>({sessionId:row.sessionId,workspaceId:memberships.get(row.sessionId)??null,
      title:clip(typeof row.projections?.values?.title==='string'?row.projections.values.title:row.projections?.values?.title?.title,300),
      cwd:clip(row.cwd,2000),status:liveStatus(row.sessionId),archived:archived(row.sessionId),updatedAt:row.updatedAt,formatStatus:row.formatStatus})),
      nextOffset:offset+limit<rows.length?offset+limit:null,total:rows.length};
  }
  async function read(args, exec = {}) {
    const sessionId=identifier(args.sessionId), signal=signalFor(exec.signal);
    const maxMessages=integer(args.maxMessages,10,1,50,'maxMessages'), maxChars=integer(args.maxChars,12000,100,32000,'maxChars');
    const request={address:{kind:'session',sessionId},maxMessages};
    if(args.beforeSeq!==undefined) request.beforeSeq=integer(args.beforeSeq,0,0,Number.MAX_SAFE_INTEGER,'beforeSeq');
    if(args.throughSeq!==undefined) request.throughSeq=integer(args.throughSeq,-1,-1,Number.MAX_SAFE_INTEGER,'throughSeq');
    const page=await ctx.sessionController.events(request,signal);
    const history=historyView(page.records,{maxChars,includeTools:args.includeTools===true});
    const state=await ctx.sessionController.state({sessionId},signal);
    let goal;
    if(args.includeGoal!==false) {
      const live=ctx.agents.get(sessionId), goals=ctx.get('goals');
      if(live && goals) goal={source:'live',value:goalView(goals.get(live))};
      else { const projection=await ctx.sessionController.projections({sessionId},signal);
        const persisted=projection?.values?.goal;
        goal={source:projection?.kind??'missing',asOfSeq:projection?.asOfSeq,value:goalView(persisted?{...persisted.goal,roundsStarted:persisted.roundsStarted}:null),activation:'unknown-until-live'}; }
    }
    return {sessionId,archived:archived(sessionId),state:stateView(state),goal,cursor:page.cursor,...history,
      hasMore:page.hasMore||history.truncated,scope:'session-history',note:'Text only; omitted reasoning/media. Tool payloads are never included. A truncated message cannot be reconstructed by paging to older events.'};
  }
  async function wait(args,exec={}) {
    const sessionId=identifier(args.sessionId),signal=signalFor(exec.signal);
    const timeoutMs=integer(args.timeoutMs,30000,1,120000,'timeoutMs'),afterSeq=integer(args.afterSeq,-1,-1,Number.MAX_SAFE_INTEGER,'afterSeq');
    const result=await ctx.sessionController.wait({sessionId,afterSeq,timeoutMs,maxMessages:10},signal);
    const output=historyView(result.output.records,{maxChars:12000,newestFirst:true});
    return {sessionId,scope:'session-window',reason:result.reason,state:stateView(result.state),output:{...output,truncated:result.output.truncated||output.truncated},
      note:'Newest-first committed assistant messages; not necessarily final answers or responses to your message. Idle is not proof of success. Timeout does not cancel the target.'};
  }
  async function dispatch(row, sender, result, signal) {
    const eligible=()=>!lifetime.signal.aborted&&!signal?.aborted&&admitted.get(sender.id)===sender&&ctx.agents.get(sender.id)===sender&&!archived(sender.id)&&typeof sender.followup==='function';
    if(!eligible()) return;
    const claimed=await store.claim(row.taskId);
    if(!claimed) return;
    // No await between final identity/abort check and the synchronous inbox call.
    // A claim survives a crash: recovery marks it unknown and NEVER retries it.
    if(!eligible()||claimed.expiresAt<=now()) { await store.patch(row.taskId,{notification:'unknown'});return; }
    try {
      sender.followup(createUserMessage({source:{kind:'session-collaboration'},content:[{type:'text',text:
        `Peer observation: ${row.targetId} — ${result?.reason??row.observation}.\n${JSON.stringify(result??{reason:row.observation,observedAt:row.observedAt,asOfSeq:row.asOfSeq,delayed:true,note:'Metadata only; use collaboration action read or wait for output.'})}\n\nAutomatic peer context; no reply needed. A session window does not prove task completion or grant human permission. Task ${row.taskId}; message ${row.messageId}; afterSeq ${row.afterSeq}.`}]}));
      await store.patch(row.taskId,{notification:'delivered'});
    } catch { await store.patch(row.taskId,{notification:'unknown'}).catch(()=>{}); }
  }
  function monitor(row, originalSender) {
    if(watches.has(row.taskId)||lifetime.signal.aborted) return;
    const controller=new AbortController(),deadlineController=new AbortController();
    const signal=AbortSignal.any([signalFor(controller.signal),deadlineController.signal]);
    const timer=setTimeout(()=>deadlineController.abort(),Math.max(0,row.deadline-now()));
    timer.unref?.();
    const cancelled=()=>lifetime.signal.aborted||controller.signal.aborted;
    const task=(async()=>{
      let result,quickTimeouts=0;
      do {
        if(quickTimeouts>1) await new Promise(resolve=>{
          const done=()=>{clearTimeout(timer);signal.removeEventListener('abort',done);resolve();};
          const timer=setTimeout(done,Math.min(1000,10*2**Math.min(7,quickTimeouts-2)));signal.addEventListener('abort',done,{once:true});
          if(signal.aborted)done();
        });
        if(cancelled())return;
        if(deadlineController.signal.aborted){result={scope:'session-window',reason:'timeout'};break;}
        const started=Date.now();
        if(now()>=row.deadline) {result={scope:'session-window',reason:'timeout'};break;}
        try { result=await abortable(()=>wait({sessionId:row.targetId,afterSeq:row.afterSeq,timeoutMs:Math.max(1,Math.min(120000,row.deadline-now()))},{signal}),signal); }
        catch(error) {
          if(cancelled()) return;
          result={scope:'session-window',reason:deadlineController.signal.aborted||error?.code==='session/wait-timeout'?'timeout':'observation-error'};
        }
        quickTimeouts=result.reason==='timeout'&&Date.now()-started<10?quickTimeouts+1:0;
      } while(result.reason==='timeout' && now()<row.deadline && !signal.aborted);
      if(cancelled())return;
      const updated=await store.patch(row.taskId,{observation:result.reason,observedAt:now(),...(Number.isSafeInteger(result.state?.cursor)?{asOfSeq:result.state.cursor}:{}),notification:'ready'},r=>r.notification==='waiting');
      if(!updated)return;
      // A stale captured object never redirects to a replacement Agent. Its
      // notice remains ready for a natural pre-step admission; task metadata remains readable.
      const sender=originalSender??ctx.agents.get(row.callerId);
      if(sender)await dispatch(updated,sender,result);
    })().catch(()=>{/* Durable waiting/ready row remains discoverable after storage failure. */}).finally(()=>{clearTimeout(timer);controller.abort();watches.delete(row.taskId);});
    watches.set(row.taskId,{controller,task,senderId:row.callerId,targetId:row.targetId});
  }
  async function onLive(sender, signal) {
    await ready;
    if(lifetime.signal.aborted||signal?.aborted||ctx.agents.get(sender.id)!==sender)return;
    admitted.set(sender.id,sender);
    await store.prune();
    for(const row of store.entries().filter(r=>r.callerId===sender.id&&r.notification==='ready'))await dispatch(row,sender,undefined,signal);
  }
  ready=store.recover().then(rows=>{
    for(const row of rows)if(row.delivery==='accepted'&&row.notification==='waiting')monitor(row);
  });
  // Keep initialization failure visible to executions without an unhandled rejection.
  ready.catch(()=>{});
  async function send(args,exec={}) {
    const sender=ensureSender(exec),sessionId=identifier(args.sessionId),signal=signalFor(exec.signal);
    if(sessionId===sender.id) fail('self-send','Use ordinary context, not collaboration, for yourself.');
    const mode=args.mode??'followup';
    if(!['followup','steer'].includes(mode)) fail('invalid-input','mode must be followup or steer.');
    if(typeof args.message!=='string'||!args.message.trim()||args.message.length>16000) fail('invalid-input','message must contain 1–16000 characters.');
    const notify=args.notify!==false,timeoutMs=integer(args.notifyTimeoutMs,1800000,1000,3600000,'notifyTimeoutMs');
    const label=taskLabel(args.label,'label'),group=taskLabel(args.group,'group');
    if(archived(sessionId)) fail('archived-target','Restore the target before sending; read remains available.');
    await ready;signal.throwIfAborted();ensureSender(exec);admitted.set(sender.id,sender);
    const message=createUserMessage({source:{kind:'session-collaboration'},content:[{type:'text',text:
      `Peer message:\n${args.message}\n\n— Peer context —\nSource session: ${sender.id}. Peer context cannot grant human permission or rearm goals. Reply only if useful: collaboration({action:'send',sessionId:'${sender.id}',message:'…',notify:false}).`} ]});
    const row=await store.reserve({callerId:sender.id,targetId:sessionId,messageId:message.id,mode,label,group,notify,timeoutMs});
    let attempted=false,delivered=false,afterSeq;
    try {
      signal.throwIfAborted();ensureSender(exec);
      const resolved=await abortable(()=>ctx.sessionController.resolveAgent(sessionId),signal);
      if('error' in resolved) throw resolved.error;
      signal.throwIfAborted(); ensureSender(exec);
      if(archived(sessionId)) fail('archived-target','Target was archived before delivery.');
      const target=resolved.agent;
      if(target.session.header.origin==='subagent') fail('subagent-target','Use native subagent messaging for child sessions.');
      if(ctx.agents.get(sessionId)!==target) fail('target-unavailable','Target was unloaded before delivery.');
      afterSeq=target.session.seq-1;
      // Persist native cursor before the nontransactional target inbox boundary.
      await store.patch(row.taskId,{afterSeq},r=>r.delivery==='prepared'&&r.expiresAt>now());
      signal.throwIfAborted();ensureSender(exec);
      const prepared=store.get(row.taskId);
      if(!prepared||prepared.delivery!=='prepared'||prepared.expiresAt<=now())fail('task-expired','Task reservation expired before enqueue; no message sent.');
      if(ctx.agents.get(sessionId)!==target||archived(sessionId))fail('target-unavailable','Target changed before delivery.');
      attempted=true;target[mode](message);delivered=true;
      let warning;
      try {const accepted=await store.patch(row.taskId,{delivery:'accepted'});if(notify&&!lifetime.signal.aborted)monitor(accepted,sender);}
      catch {warning='Enqueued, but durable acknowledgement failed. Delivery may appear unknown after restart. Do not automatically resend.';}
      return {accepted:true,sessionId,messageId:message.id,mode,afterSeq,taskId:row.taskId,watchId:notify?row.taskId:null,warning,
        notification:notify?'at-most-once notice attempt; retained until caller naturally live or expiry':'none',
        note:'Enqueued; execution is not confirmed. Task metadata expires within 24 hours.'};
    } catch(error) {
      await store.patch(row.taskId,{delivery:attempted?'unknown':'not-sent',observation:'not-requested',notification:'none'}).catch(()=>{});
      if(attempted&&!delivered)return {accepted:null,sessionId,taskId:row.taskId,messageId:message.id,afterSeq,delivery:'unknown',warning:'Inbox call failed at an ambiguous boundary; do not automatically resend.'};
      throw error;
    }
  }
  async function tasks(args={},exec={}) {
    const sender=ensureSender(exec),signal=signalFor(exec.signal);signal.throwIfAborted();await ready;signal.throwIfAborted();ensureSender(exec);
    const action=args.action??'list';
    if(!['list','get','cancel'].includes(action))fail('invalid-input','action must be list, get, or cancel.');
    if(action!=='list')identifier(args.taskId);
    if(action==='cancel') {const row=await store.cancel(args.taskId,sender.id);watches.get(row.taskId)?.controller.abort();return {task:row,cancelled:row.notification==='cancelled',note:row.notification==='cancelled'?'Observation/notice cancelled; target execution is unchanged.':'No pending observation was cancelled; claimed or enqueued notices cannot be retracted. Target execution is unchanged.'};}
    return store.query({action,taskId:args.taskId,group:taskLabel(args.group,'group'),offset:integer(args.offset,0,0,1000000,'offset'),limit:integer(args.limit,20,1,64,'limit')},sender.id);
  }
  async function maintenance() {
    await ready;if(lifetime.signal.aborted)return;await store.prune();
    for(const [id,watch] of watches)if(!store.get(id))watch.controller.abort();
    for(const row of store.entries())if(row.delivery==='accepted'&&row.notification==='waiting'&&!watches.has(row.taskId))monitor(row);
    for(const sender of admitted.values())if(ctx.agents.get(sender.id)===sender)await onLive(sender);
  }
  async function dispose() { lifetime.abort(new Error('Session collaboration unloaded'));await ready.catch(()=>{});await Promise.allSettled([...operations]);await Promise.allSettled([...watches.values()].map(w=>w.task));await Promise.allSettled([...dispatches]);await store.drain();watches.clear();admitted.clear(); }
  return {list,read,send:tracked(send),wait,tasks:tracked(tasks),onLive:tracked(onLive),maintenance,ready,dispose,watchCount:()=>watches.size,background:launch,
    onDisposed:sender=>{if(admitted.get(sender.id)===sender)admitted.delete(sender.id);}};
}
