import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { createCollaboration, historyView } from './core.js';
import { createTaskStore, memoryTaskTable } from './tasks.js';
import { createWaitMany } from './wait-many.js';

// Only in-memory synthetic objects. Does not use Host services or run a model.
export async function selfTest() {
  const deliveries=[],calls=[];
  const makeAgent=id=>({id,status:'idle',session:{seq:4,header:{cwd:'/synthetic'}},followup(message){deliveries.push({id,mode:'followup',message});},steer(message){deliveries.push({id,mode:'steer',message});}});
  const sender=makeAgent('fixture-sender'),target=makeAgent('fixture-target');
  const agents=new Map([[sender.id,sender],[target.id,target]]);
  let waiter;
  const ctx={agents:{get:id=>agents.get(id)},get:()=>undefined,
    workspaceRegistry:{archivedSessionIds:['fixture-archived'],list:()=>[{id:'fixture-project',title:'Fixture',path:'/synthetic',sessionIds:[target.id,'fixture-archived']}]},
    sessionController:{
      async list(){calls.push('list');return{items:[{sessionId:target.id,cwd:'/synthetic',updatedAt:1},{sessionId:'fixture-archived',updatedAt:0}]};},
      async resolveAgent(id){calls.push('resolve');return id===target.id?{agent:target}:{error:new Error('fixture missing')};},
      async events(request){calls.push('events');assert.equal(request.address.sessionId,target.id);return{cursor:3,hasMore:false,records:[{type:'event',event:{seq:3,type:'assistant/message',surfaceOp:'append',data:{message:{id:'m',content:[{type:'text',text:'fixture output'}]}}}}]};},
      async state(){return{cursor:3,active:false,running:false,queue:null,pendingInput:[]};},
      async projections(){calls.push('goal');return{kind:'sequenced',asOfSeq:3,values:{goal:{goal:{id:'fixture-goal',phase:'active',objective:'Synthetic goal',revision:1},roundsStarted:0}}};},
      async wait(request,signal){calls.push('wait');if(waiter)return waiter(request,signal);return{reason:'idle',state:{cursor:4,active:true,running:false,queue:[],pendingInput:[]},output:{records:[],truncated:false}};}
    }};
  const factory=value=>({id:randomUUID(),role:'user',...value});
  const api=createCollaboration(ctx,factory);
  try {
    assert.equal((await api.list({kind:'sessions'})).items.length,1);
    assert.equal((await api.list({kind:'sessions',includeArchived:true})).items.length,2);
    const read=await api.read({sessionId:target.id});
    assert.equal(read.goal.value.phase,'active');assert.equal(read.goal.value.id,'fixture-goal');assert.equal(read.goal.value.objective,'Synthetic goal');assert.equal(read.goal.value.activation,undefined);assert.equal(read.goal.activation,'unknown-until-live');
    assert.equal(calls.includes('resolve'),false);
    assert.equal(read.records[0].text,'fixture output');
    const sent=await api.send({sessionId:target.id,message:'fixture only',notify:false},{agent:sender});
    assert.equal(sent.afterSeq,3);assert.equal(deliveries[0].message.source.kind,'session-collaboration');
    assert.equal(deliveries[0].message.role,'user');
    await api.send({sessionId:target.id,message:'steer fixture',mode:'steer',notify:false},{agent:sender});
    assert.equal(deliveries[1].mode,'steer');
    await assert.rejects(api.send({sessionId:sender.id,message:'no'},{agent:sender}),{code:'self-send'});
    await assert.rejects(api.send({sessionId:'fixture-archived',message:'no'},{agent:sender}),{code:'archived-target'});
    await assert.rejects(api.send({sessionId:target.id,message:'no'},{agent:{id:sender.id}}),{code:'sender-unavailable'});
    const clipped=historyView([{event:{seq:1,type:'assistant/message',surfaceOp:'append',data:{message:{content:[{type:'text',text:'12345'},{type:'text',text:'678'}]}}}}],{maxChars:5});
    assert.equal(clipped.truncated,true);assert.equal(clipped.records[0].textTruncated,true);
    const notice=await api.send({sessionId:target.id,message:'notice fixture'},{agent:sender});
    // Drain only already-settling promise reactions; no timers or background work.
    for(let i=0;i<40;i++) await Promise.resolve();
    assert.ok(notice.watchId);assert.equal(api.watchCount(),0);
    assert.equal(deliveries.filter(d=>d.id===sender.id).length,1);
    let aborted=false;
    waiter=(_request,signal)=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>{aborted=true;reject(signal.reason);},{once:true}));
    await api.send({sessionId:target.id,message:'dispose fixture'},{agent:sender});
    assert.equal(api.watchCount(),1);
    await api.dispose();assert.equal(aborted,true);assert.equal(api.watchCount(),0);
    const table=memoryTaskTable(),store=createTaskStore(table);
    const prepared=await store.reserve({callerId:sender.id,targetId:target.id,messageId:'synthetic',mode:'followup',notify:true,timeoutMs:1000});
    const recovered=await createTaskStore(table).recover();assert.equal(recovered[0].taskId,prepared.taskId);assert.equal(recovered[0].delivery,'unknown');
    waiter=undefined;
    const next=createCollaboration(ctx,factory,{table}),many=createWaitMany(ctx);
    try {
      const tracked=await next.tasks({action:'get',taskId:prepared.taskId},{agent:sender});assert.equal(tracked.delivery,'unknown');
      const sent=await next.send({sessionId:target.id,message:'tracked fixture',notify:false,label:'fixture',group:'synthetic'},{agent:sender});assert.ok(sent.taskId);
      assert.equal((await next.tasks({group:'synthetic'},{agent:sender})).total,1);
      const observed=await many.waitMany({targets:[{sessionId:target.id,afterSeq:sent.afterSeq}],mode:'all',timeoutMs:1000});assert.equal(observed.reason,'all');assert.equal(observed.results[0].reason,'idle');
    } finally {await next.dispose();await many.dispose();}
    return {ok:true,kind:'synthetic-only',checks:24,nativeHost:false,modelCalls:0,sessionWrites:0};
  } finally {await api.dispose();}
}
