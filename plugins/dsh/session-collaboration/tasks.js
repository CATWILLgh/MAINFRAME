import { randomUUID } from 'node:crypto';

export const TASK_LIMITS = Object.freeze({perCaller:64,total:256,pendingPerCaller:8,pendingTotal:32,ttlMs:86400000});
const pending = row => ['waiting','ready'].includes(row.notification) || row.delivery==='prepared';
const error = (code,message) => Object.assign(new Error(message),{code});
export function taskLabel(value,name) {
  if(value===undefined) return undefined;
  if(typeof value!=='string'||!value.trim()||value.length>120) throw error('invalid-input',`${name} must contain 1–120 characters.`);
  return value;
}
// The adapter stores metadata only. Every mutating operation is serialized, including
// cap checks and notice claims. Failed writes never publish optimistic local state.
export function createTaskStore(table, {now=Date.now,limits=TASK_LIMITS}={}) {
  let tail=Promise.resolve();
  const serial=fn=>{const run=tail.then(fn);tail=run.catch(()=>{});return run;};
  const rows=()=>Array.from(table.entries(),([,row])=>row);
  const put=async row=>{await table.put(row.taskId,row);return row;};
  async function prune() {const expired=rows().filter(r=>r.expiresAt<=now()).map(r=>r.taskId);if(expired.length)await table.deleteMany(expired);}
  const owned=(id,callerId)=>{const row=table.get(id);if(!row||row.callerId!==callerId)throw error('task-not-found','Task not found for this caller.');return row;};
  return {
    recover:()=>serial(async()=>{await prune();for(const row of rows()) {
      if(row.delivery==='prepared') await put({...row,delivery:'unknown',observation:'not-requested',notification:'none',updatedAt:now()});
      else if(row.notification==='claimed') await put({...row,notification:'unknown',updatedAt:now()});
    }return rows();}),
    reserve:input=>serial(async()=>{
      await prune();let all=rows(),own=all.filter(r=>r.callerId===input.callerId);
      if(input.notify && (all.filter(r=>['waiting','ready'].includes(r.notification)).length>=limits.pendingTotal || own.filter(r=>['waiting','ready'].includes(r.notification)).length>=limits.pendingPerCaller)) throw error('watch-limit','Too many pending notices; cancel observation or wait for delivery/expiry.');
      const evict=async candidates=>{const row=candidates.filter(r=>!pending(r)).sort((a,b)=>a.updatedAt-b.updatedAt)[0];if(!row)throw error('task-limit','Task retention capacity is full; pending tasks are never evicted.');await table.deleteMany([row.taskId]);};
      if(own.length>=limits.perCaller)await evict(own);
      all=rows();if(all.length>=limits.total)await evict(all);
      const time=now();
      return put({taskId:randomUUID(),callerId:input.callerId,targetId:input.targetId,messageId:input.messageId,
        mode:input.mode, ...(input.label===undefined?{}:{label:input.label}),...(input.group===undefined?{}:{group:input.group}),
        createdAt:time,updatedAt:time,expiresAt:time+limits.ttlMs,deadline:time+input.timeoutMs,
        delivery:'prepared',observation:input.notify?'waiting':'not-requested',notification:input.notify?'waiting':'none'});
    }),
    patch:(id,changes,guard=()=>true)=>serial(async()=>{const row=table.get(id);if(!row||!guard(row))return undefined;return put({...row,...changes,updatedAt:now()});}),
    claim:(id)=>serial(async()=>{const row=table.get(id);if(!row||row.expiresAt<=now()||row.notification!=='ready')return undefined;return put({...row,notification:'claimed',updatedAt:now()});}),
    cancel:(id,callerId)=>serial(async()=>{await prune();const row=owned(id,callerId);if(row.delivery==='prepared')throw error('task-busy','Send is still in progress; retry observation cancellation after it settles.');
      if(!pending(row))return row;return put({...row,observation:row.observation==='waiting'?'cancelled':row.observation,notification:'cancelled',updatedAt:now()});}),
    query:(args,callerId)=>serial(async()=>{await prune();if(args.action==='get')return owned(args.taskId,callerId);
      const items=rows().filter(r=>r.callerId===callerId&&(args.group===undefined||r.group===args.group)).sort((a,b)=>b.createdAt-a.createdAt||a.taskId.localeCompare(b.taskId));
      return {items:items.slice(args.offset,args.offset+args.limit),total:items.length,nextOffset:args.offset+args.limit<items.length?args.offset+args.limit:null,limits};}),
    entries:rows, get:id=>table.get(id), prune:()=>serial(prune), drain:()=>tail,
  };
}
// Used only by synthetic tests and direct core consumers; production supplies a
// storageDomain table explicitly and never silently falls back after a failure.
export function memoryTaskTable(seed=[]) {
  const data=new Map(seed.map(row=>[row.taskId,structuredClone(row)]));
  return {entries:()=>data.entries(),get:id=>data.get(id),put:async(id,row)=>{data.set(id,structuredClone(row));},deleteMany:async ids=>{for(const id of ids)data.delete(id);}};
}
