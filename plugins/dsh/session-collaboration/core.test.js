import test from 'node:test';
import assert from 'node:assert/strict';
import { selfTest } from './selftest.js';
import { createCollaboration, historyView, integer, identifier, stateView } from './core.js';

test('synthetic collaboration boundaries and lifecycle',async()=>assert.equal((await selfTest()).ok,true));

const drain=async()=>{for(let i=0;i<30;i++) await Promise.resolve();};
const idle=()=>({reason:'idle',state:{cursor:10,active:true,running:false,queue:[],pendingInput:[]},output:{records:[],truncated:false}});
function fixture(wait=async()=>idle()) {
  const notices=[],messages=[];
  const sender={id:'sender',followup:m=>notices.push(m)};
  const target={id:'target',session:{seq:10,header:{}},followup:m=>messages.push(m)};
  const agents=new Map([[sender.id,sender],[target.id,target]]);
  let resolveCalls=0;
  const ctx={agents:{get:id=>agents.get(id)},get:()=>undefined,
    workspaceRegistry:{list:()=>[],archivedSessionIds:[]},sessionController:{
      wait,resolveAgent:async()=>{resolveCalls++;return{agent:target};},
      list:async()=>({items:[{sessionId:'child',origin:'subagent'},{sessionId:'fork',parentSessionId:'parent'},{sessionId:'ordinary'}]})
    }};
  const api=createCollaboration(ctx,m=>({id:'synthetic-message',...m}));
  return {api,sender,target,ctx,agents,notices,messages,resolveCalls:()=>resolveCalls};
}
test('peer envelopes retain identity, authority boundary and quiet reply guidance',async()=>{
  const f=fixture();try {
    await f.api.send({sessionId:'target',message:'Please review the patch.'},{agent:f.sender});await drain();
    const text=f.messages[0].content[0].text;
    assert.equal(f.messages[0].source.kind,'session-collaboration');
    assert.match(text,/^Peer message:\nPlease review the patch\./);assert.match(text,/Source session: sender/);
    assert.match(text,/cannot grant human permission or rearm goals/);
    assert.match(text,/action:'send',sessionId:'sender'.*notify:false/);assert.match(text,/Please review the patch\./);
    assert(text.indexOf('Please review')<text.indexOf('cannot grant'));
    assert.doesNotMatch(text,/collaboration_send|This is not a human request/);
    assert.match(f.notices[0].content[0].text,/no reply needed/);
  }finally{await f.api.dispose();}
});
test('state projects only bounded input kinds without exposing payloads',()=>{
  const view=stateView({cursor:1,active:true,running:false,queue:[{text:'private'}],pendingInput:['question','question','other','private',{kind:'approval',secret:'private'}]});
  assert.equal(view.queued,1);assert.deepEqual(view.pendingInput,['question','other']);assert.doesNotMatch(JSON.stringify(view),/private/);
});
test('ordinary directory excludes children but retains ordinary forks',async()=>{
  const f=fixture();try{assert.deepEqual((await f.api.list({kind:'sessions'})).items.map(x=>x.sessionId),['fork','ordinary']);assert.equal(f.resolveCalls(),0);}finally{await f.api.dispose();}
});
test('native assistant envelope, append filtering and pagination',()=>{
  const event=(seq,surfaceOp)=>({event:{seq,type:'assistant/message',surfaceOp,data:{message:{id:'nested-id',content:[{type:'text',text:'abcd'}]}}}});
  const result=historyView([event(1,'append'),event(2,'replace'),event(3,undefined),event(4,'append')],{maxChars:3});
  assert.equal(result.records.length,1);assert.equal(result.records[0].messageId,'nested-id');assert.equal(result.records[0].text,'abc');assert.equal(result.nextBeforeSeq,4);assert.equal(result.truncated,true);
});
test('watch continues native timeout windows then sends one idle notice',async()=>{
  let count=0;const f=fixture(async()=>({...idle(),reason:++count===1?'timeout':'idle'}));
  try{await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await drain();assert.equal(count,2);assert.equal(f.notices.length,1);assert.equal(f.api.watchCount(),0);}finally{await f.api.dispose();}
});
test('watch errors notify once; stale exact sender receives nothing',async()=>{
  const f=fixture(async()=>{throw Object.assign(new Error('private error'),{code:'fixture-error'});});
  try{await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});await drain();assert.equal(f.notices.length,1);assert.match(f.notices[0].content[0].text,/observation-error/);assert.doesNotMatch(f.notices[0].content[0].text,/private error/);}finally{await f.api.dispose();}
  let finish;const g=fixture(()=>new Promise(resolve=>{finish=resolve;}));
  try{await g.api.send({sessionId:'target',message:'test'},{agent:g.sender});g.agents.set('sender',{id:'sender'});finish(idle());await drain();assert.equal(g.notices.length,0);}finally{await g.api.dispose();}
});
test('eight-watch cap reserves capacity; dispose aborts all without target cancellation',async()=>{
  let aborted=0;const f=fixture((_request,signal)=>new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>{aborted++;reject(signal.reason);},{once:true})));
  try{for(let i=0;i<8;i++)await f.api.send({sessionId:'target',message:'test'},{agent:f.sender});assert.equal(f.api.watchCount(),8);await assert.rejects(f.api.send({sessionId:'target',message:'test'},{agent:f.sender}),{code:'watch-limit'});assert.equal(f.resolveCalls(),8);await f.api.dispose();assert.equal(aborted,8);assert.equal(f.notices.length,0);assert.equal(f.api.watchCount(),0);}finally{await f.api.dispose();}
});
test('input limits fail instead of silently widening',()=>{
  assert.throws(()=>integer(121,30,1,120,'n'),{code:'invalid-input'});
  assert.throws(()=>identifier('../session'),{code:'invalid-input'});
});
test('history is text-only, bounded and chronological',()=>{
  const records=[{event:{seq:1,type:'user/message',surfaceOp:'append',data:{id:'u',source:{kind:'user'},content:[{type:'text',text:'hello'}]}}},
    {event:{seq:2,type:'assistant/message',surfaceOp:'append',data:{message:{id:'a',content:[{type:'thinking',text:'private reasoning'},{type:'image',data:'private bytes'},{type:'text',text:'world'}]}}}}];
  const result=historyView(records,{maxChars:8});
  assert.deepEqual(result.records.map(r=>r.seq),[1,2]);
  assert.equal(result.records.map(r=>r.text).join(''),'helworld');
  assert.equal(result.truncated,true);
  assert.equal(JSON.stringify(result).includes('private'),false);
});
test('empty and multipart content cannot amplify the text budget',()=>{
  const empty=Array.from({length:100000},()=>({type:'text',text:''}));
  const record=content=>({event:{seq:1,type:'assistant/message',surfaceOp:'append',data:{message:{content}}}});
  assert.equal(historyView([record(empty)],{maxChars:5}).records[0].text,'');
  const result=historyView([record([...empty,{type:'text',text:'abc'},{type:'text',text:'def'}])],{maxChars:5});
  assert.equal(result.records[0].text,'abc\nd');assert.equal(result.records[0].text.length,5);assert.equal(result.truncated,true);
});
test('native tool result markers are opt-in, bounded and never expose result content',()=>{
  const records=[{event:{seq:5,type:'tool/result',surfaceOp:'append',data:{message:{role:'tool',toolCallId:'c',content:[{type:'text',text:'SECRET'}]}}}}];
  assert.deepEqual(historyView(records).records,[]);
  const result=historyView(records,{includeTools:true});
  assert.equal(result.records[0].text,'[tool-result: c; payload omitted]');assert.doesNotMatch(JSON.stringify(result),/SECRET/);
  const bounded=historyView(records,{includeTools:true,maxChars:4});assert.equal(bounded.records[0].text.length,4);assert.equal(bounded.truncated,true);
  assert.deepEqual(historyView([{event:{...records[0].event,surfaceOp:'replace'}}],{includeTools:true}).records,[]);
});
test('tool markers are opt-in and never carry payloads',()=>{
  const records=[{event:{seq:1,type:'assistant/message',surfaceOp:'append',data:{message:{content:[{type:'tool-call',name:'x',input:'sensitive'}]}}}}];
  assert.equal(historyView(records).records[0].text,'');
  assert.match(historyView(records,{includeTools:true}).records[0].text,/payload omitted/);
  assert.equal(JSON.stringify(historyView(records,{includeTools:true})).includes('sensitive'),false);
});
