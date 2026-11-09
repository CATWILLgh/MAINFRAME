import test from 'node:test';
import assert from 'node:assert/strict';
import { createTaskStore, memoryTaskTable, TASK_LIMITS } from './tasks.js';
import { createCollaboration } from './core.js';

const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
const idle=()=>({reason:'idle',state:{cursor:10,active:true,running:false,queue:[],pendingInput:[]},output:{records:[],truncated:false}});
const input={callerId:'sender',targetId:'target',messageId:'message',mode:'followup',notify:true,timeoutMs:1000};
function fixture({table=memoryTaskTable(),now=Date.now,wait=async()=>idle()}={}) {
  const notices=[],messages=[];
  const sender={id:'sender',followup:m=>notices.push(m)},target={id:'target',session:{seq:10,header:{}},followup:m=>messages.push(m)};
  const agents=new Map([[sender.id,sender],[target.id,target]]);let resolves=0;
  const ctx={agents:{get:id=>agents.get(id),list:()=>[...agents.values()]},workspaceRegistry:{archivedSessionIds:[]},sessionController:{wait,resolveAgent:async()=>{resolves++;return{agent:target};}}};
  const api=createCollaboration(ctx,m=>({id:'message',...m}),{table,now});
  return {api,sender,target,agents,notices,messages,ctx,table,resolves:()=>resolves};
}

test('terminal observation clears its deadline timer and aborts observer signal',async t=>{
  const clear=t.mock.method(globalThis,'clearTimeout');let signal;
  const f=fixture({wait:async(_request,s)=>{signal=s;return idle();}});
  try {
    await f.api.send({sessionId:'target',message:'test',notifyTimeoutMs:3600000},{agent:f.sender});await flush();
    assert.equal(f.api.watchCount(),0);assert.equal(f.notices.length,1);assert.equal(signal.aborted,true);
    assert.equal(clear.mock.callCount(),1);
  }finally{await f.api.dispose();}
});
test('hard observer deadline ends noncooperative native wait and releases its timer',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  let signal,finish;const f=fixture({wait:(_request,s)=>{signal=s;return new Promise(resolve=>{finish=resolve;});}});
  try {
    const sent=await f.api.send({sessionId:'target',message:'test',notifyTimeoutMs:1000},{agent:f.sender});
    await flush();assert.equal(f.api.watchCount(),1);
    t.mock.timers.tick(1000);await flush();
    assert.equal(signal.aborted,true);assert.equal(f.api.watchCount(),0);
    assert.equal(f.table.get(sent.taskId).observation,'timeout');assert.equal(f.notices.length,1);
    finish(idle());await flush();assert.equal(f.notices.length,1);
  } finally {await f.api.dispose();}
});
test('dispose races stalled native resolve and completes writes before storage closes',async()=>{
  const f=fixture();let resolve;f.ctx.sessionController.resolveAgent=()=>new Promise(done=>resolve=done);
  const pending=f.api.send({sessionId:'target',message:'test'},{agent:f.sender});const rejection=assert.rejects(pending);await flush();assert.equal(typeof resolve,'function');
  await f.api.dispose();await rejection;const rows=JSON.stringify([...f.table.entries()]);resolve({agent:f.target});await flush();assert.equal(f.messages.length,0);assert.equal(JSON.stringify([...f.table.entries()]),rows);assert.equal([...f.table.entries()][0][1].delivery,'not-sent');
});
test('expired reservation cannot enqueue even after stalled resolve completes',async()=>{
  let time=10000;const f=fixture({now:()=>time});f.ctx.sessionController.resolveAgent=async()=>{time+=TASK_LIMITS.ttlMs;return{agent:f.target};};
  await assert.rejects(f.api.send({sessionId:'target',message:'test'},{agent:f.sender}),{code:'task-expired'});assert.equal(f.messages.length,0);await f.api.dispose();
});
test('ready recovery waits natural admission; maintenance and aborted admission cannot dispatch',async()=>{
  const table=memoryTaskTable(),store=createTaskStore(table);const row=await store.reserve(input);await store.patch(row.taskId,{delivery:'accepted',afterSeq:9,observation:'idle',notification:'ready'});
  const f=fixture({table});await f.api.ready;await f.api.maintenance();assert.equal(f.notices.length,0);const controller=new AbortController();controller.abort();await f.api.onLive(f.sender,controller.signal);assert.equal(f.notices.length,0);
  await f.api.onLive(f.sender);assert.equal(f.notices.length,1);const cancelled=await f.api.tasks({action:'cancel',taskId:row.taskId},{agent:f.sender});assert.equal(cancelled.cancelled,false);assert.match(cancelled.note,/cannot be retracted/);await f.api.dispose();
});
test('prepared restart is delivery unknown, never replayed or observed',async()=>{
  const table=memoryTaskTable(),store=createTaskStore(table);const row=await store.reserve(input);
  const f=fixture({table});await f.api.ready;await flush();
  const restored=await f.api.tasks({action:'get',taskId:row.taskId},{agent:f.sender});
  assert.equal(restored.delivery,'unknown');assert.equal(restored.notification,'none');assert.equal(f.resolves(),0);assert.equal(f.messages.length,0);await f.api.dispose();
});
test('claimed restart is unknown and duplicate notice is never attempted',async()=>{
  const table=memoryTaskTable(),store=createTaskStore(table);const row=await store.reserve(input);
  await store.patch(row.taskId,{delivery:'accepted',afterSeq:9,observation:'idle',notification:'ready'});await store.claim(row.taskId);
  const f=fixture({table});await f.api.onLive(f.sender);await f.api.onLive(f.sender);
  assert.equal(f.notices.length,0);assert.equal((await f.api.tasks({action:'get',taskId:row.taskId},{agent:f.sender})).notification,'unknown');await f.api.dispose();
});
test('restart resumes bounded observation without activation and retains unloaded-caller notice',async()=>{
  let time=10000;const table=memoryTaskTable(),store=createTaskStore(table,{now:()=>time});const row=await store.reserve(input);
  await store.patch(row.taskId,{delivery:'accepted',afterSeq:9});
  const f=fixture({table,now:()=>time});f.agents.delete('sender');await f.api.ready;await flush();
  assert.equal(table.get(row.taskId).notification,'ready');assert.equal(f.resolves(),0);assert.equal(f.notices.length,0);
  f.agents.set('sender',f.sender);await Promise.all([f.api.onLive(f.sender),f.api.onLive(f.sender)]);
  assert.equal(f.notices.length,1);assert.match(f.notices[0].content[0].text,/"delayed":true/);assert.equal(table.get(row.taskId).notification,'delivered');await f.api.dispose();
});
test('restart deadline preserves timeout and TTL drops old metadata',async()=>{
  let time=10000,waits=0;const table=memoryTaskTable(),store=createTaskStore(table,{now:()=>time});const row=await store.reserve(input);await store.patch(row.taskId,{delivery:'accepted',afterSeq:9});
  time+=2000;const f=fixture({table,now:()=>time,wait:async()=>{waits++;return idle();}});f.agents.delete('sender');await f.api.ready;await flush();
  assert.equal(waits,0);assert.equal(table.get(row.taskId).observation,'timeout');time+=TASK_LIMITS.ttlMs;await f.api.maintenance();assert.equal(table.get(row.taskId),undefined);await f.api.dispose();
});
test('storage prepare failure prevents activation and enqueue',async()=>{
  const table=memoryTaskTable();table.put=async()=>{throw new Error('storage offline');};const f=fixture({table});
  await assert.rejects(f.api.send({sessionId:'target',message:'do not persist body'},{agent:f.sender}),/storage offline/);assert.equal(f.resolves(),0);assert.equal(f.messages.length,0);await f.api.dispose();
});
test('ack storage failure after enqueue returns accepted and warns, never retries',async()=>{
  const table=memoryTaskTable(),put=table.put;table.put=async(id,row)=>{if(row.delivery==='accepted')throw new Error('offline');return put(id,row);};const f=fixture({table});
  const result=await f.api.send({sessionId:'target',message:'secret payload'},{agent:f.sender});await flush();
  assert.equal(result.accepted,true);assert.match(result.warning,/Do not automatically resend/);assert.equal(f.messages.length,1);assert.equal(f.notices.length,0);
  assert.equal(JSON.stringify([...table.entries()]).includes('secret payload'),false);await f.api.dispose();
});
test('failed inbox boundary returns ambiguous, never automatically resends',async()=>{
  const f=fixture();f.target.followup=()=>{throw new Error('unknown inbox state');};const result=await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});
  assert.equal(result.accepted,null);assert.equal(result.delivery,'unknown');assert.equal((await f.api.tasks({action:'get',taskId:result.taskId},{agent:f.sender})).delivery,'unknown');await f.api.dispose();
});
test('aborted send before enqueue records not-sent and suppresses observation',async()=>{
  const f=fixture(),controller=new AbortController();f.ctx.sessionController.resolveAgent=async()=>{controller.abort();return{agent:f.target};};
  await assert.rejects(f.api.send({sessionId:'target',message:'test'},{agent:f.sender,signal:controller.signal}));
  assert.equal(f.messages.length,0);assert.equal((await f.api.tasks({}, {agent:f.sender})).items[0].delivery,'not-sent');await f.api.dispose();
});
test('observation cancel is owner-only, leaves target execution untouched',async()=>{
  let aborted=0;const f=fixture({wait:(_args,signal)=>new Promise((_r,reject)=>signal.addEventListener('abort',()=>{aborted++;reject(signal.reason);},{once:true}))});
  const sent=await f.api.send({sessionId:'target',message:'test',label:'short',group:'batch'},{agent:f.sender});const other={id:'other'};f.agents.set('other',other);
  for(const action of ['get','cancel'])await assert.rejects(f.api.tasks({action,taskId:sent.taskId},{agent:other}),{code:'task-not-found'});
  assert.equal((await f.api.tasks({}, {agent:other})).total,0);
  const cancelled=await f.api.tasks({action:'cancel',taskId:sent.taskId},{agent:f.sender});await flush();assert.equal(cancelled.task.notification,'cancelled');assert.equal(aborted,1);assert.equal(f.messages.length,1);assert.equal(f.notices.length,0);
  assert.equal((await f.api.tasks({group:'batch'},{agent:f.sender})).total,1);assert.equal((await f.api.tasks({group:'else'},{agent:f.sender})).total,0);await f.api.dispose();
});
test('ready unloaded notices consume cap; cancellation releases it',async()=>{
  const f=fixture();f.agents.delete('target');f.agents.set('target',f.target);
  // Keep caller live for send validation, unload it only after each synchronous send.
  for(let i=0;i<8;i++) {
    const row=await createTaskStore(f.table).reserve(input);await createTaskStore(f.table).patch(row.taskId,{delivery:'accepted',afterSeq:9,observation:'idle',notification:'ready'});
  }
  await assert.rejects(f.api.send({sessionId:'target',message:'test'},{agent:f.sender}),{code:'watch-limit'});assert.equal(f.resolves(),0);
  const row=[...f.table.entries()][0][1];await f.api.tasks({action:'cancel',taskId:row.taskId},{agent:f.sender});await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await f.api.dispose();
});
test('caps serialize concurrent sends, evict only terminal metadata, expire at absolute TTL',async()=>{
  let time=1000;const table=memoryTaskTable(),limits={...TASK_LIMITS,perCaller:2,total:3,pendingPerCaller:2,pendingTotal:3};const store=createTaskStore(table,{limits,now:()=>time});
  const reserved=await Promise.allSettled([store.reserve(input),store.reserve(input),store.reserve(input)]);assert.equal(reserved.filter(r=>r.status==='fulfilled').length,2);assert.equal(reserved[2].reason.code,'watch-limit');
  await assert.rejects(store.reserve({...input,notify:false}),{code:'task-limit'});
  const first=reserved[0].value;await store.patch(first.taskId,{delivery:'accepted',notification:'delivered',observation:'idle'});time++;
  await store.reserve({...input,notify:false});assert.equal(table.get(first.taskId),undefined);assert.equal([...table.entries()].length,2);
  time+=TASK_LIMITS.ttlMs;await store.prune();assert.equal([...table.entries()].length,0);
});
test('claim failure suppresses dispatch and persists retryable ready state',async()=>{
  const table=memoryTaskTable(),put=table.put;table.put=async(id,row)=>{if(row.notification==='claimed')throw new Error('offline');return put(id,row);};const f=fixture({table});
  const sent=await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await flush();assert.equal(f.notices.length,0);assert.equal(table.get(sent.taskId).notification,'ready');await f.api.dispose();
});
test('live replacement during claim never receives stale notice and claim is not replayed',async()=>{
  const table=memoryTaskTable(),put=table.put;let f;table.put=async(id,row)=>{await put(id,row);if(row.notification==='claimed')f.agents.set('sender',{id:'sender',followup:m=>f.notices.push(m)});};f=fixture({table});
  const sent=await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await flush();assert.equal(f.notices.length,0);assert.equal(table.get(sent.taskId).notification,'unknown');await f.api.onLive(f.agents.get('sender'));assert.equal(f.notices.length,0);await f.api.dispose();
});
test('disposal keeps durable observation for restart and aborts no target',async()=>{
  let aborted=0;const table=memoryTaskTable(),f=fixture({table,wait:(_args,signal)=>new Promise((_r,reject)=>signal.addEventListener('abort',()=>{aborted++;reject(signal.reason);},{once:true}))});
  const sent=await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await f.api.dispose();assert.equal(aborted,1);assert.equal(table.get(sent.taskId).notification,'waiting');assert.equal(f.messages.length,1);
  const g=fixture({table});await g.api.ready;await flush();assert.equal(g.messages.length,0);assert.equal(g.notices.length,0);await g.api.onLive(g.sender);assert.equal(g.notices.length,1);await g.api.dispose();
});
