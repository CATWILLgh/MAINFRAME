import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { createCollaborationTool, collaborationSchema } from './tool-surface.js';

test('storage domain name meets native defineDomain identifier contract',async()=>{
  const source=await readFile(new URL('./storage.js',import.meta.url),'utf8');
  const name=source.match(/defineDomain\(\{name:'([^']+)'/)?.[1];
  assert.equal(name,'mainframe_session_collaboration');
  assert.match(name,/^[a-z][a-z0-9_]*$/);
});

// Exercise registration/lifecycle orchestration without importing native packages,
// opening domains, or touching any real Agent/session/profile.
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
async function fixture({ready=Promise.resolve(),onLive=async()=>{},open,drain,failCreate=false,failRegister=false,failDispose=false}={}) {
  const source=(await readFile(new URL('./index.js',import.meta.url),'utf8')).replace(/^import .*;\n/gm,'').replace(/export /g,'');
  const events=new Map(),tools=[],calls=[],effects=[];let active=true;
  const assertActive=()=>{if(!active)throw new Error('inactive effect');};
  // Model Cordis ownership: setup is awaited, returned functions are disposers,
  // unload waits every effect and does NOT emit an ordinary "dispose" event.
  const ctx={on:(event,fn)=>{assertActive();events.set(event,fn);effects.push(async()=>events.delete(event));},effect:fn=>{
    assertActive();const task=Promise.resolve(fn());task.catch(()=>{});
    let disposed;const dispose=()=>disposed??=task.then(fn=>fn?.(),()=>{});effects.push(dispose);
    return Object.assign(()=>dispose(),{then:(resolve,reject)=>task.then(()=>()=>dispose()).then(resolve,reject)});
  },tools:{register:tool=>{assertActive();if(failRegister)throw new Error('registration failed');tools.push(tool);return ()=>{tools.splice(tools.indexOf(tool),1);};}}};
  const api={ready,onLive:async(...args)=>{calls.push('live');return onLive(...args);},onDisposed:()=>calls.push('agent-disposed'),dispose:()=>{calls.push('api-dispose');if(failDispose)throw new Error('disposal failed');return drain;},background:fn=>fn(),maintenance:async()=>calls.push('maintenance')};
  const initialize=vm.runInNewContext(source+';apply(ctx)',{ctx,normalizeSessionTitle:()=>{},createCollaborationTool,createUserMessage:()=>{},createCollaboration:()=>{if(failCreate)throw new Error('construction failed');return api;},createWaitMany:()=>({dispose:async()=>calls.push('many-dispose')}),createLifecycleManagement:()=>({session:async args=>({action:args.action}),dispose:async()=>calls.push('lifecycle-dispose')}),openTaskDomain:async()=>{await open;return {table:()=>({}),close:async()=>calls.push('domain-close')};},setInterval:()=>({unref(){}}),clearInterval:()=>calls.push('timer-clear')});
  initialize.catch(()=>{});
  const dispose=async()=>{active=false;await Promise.all(effects.splice(0).reverse().map(fn=>fn()));};
  return {events,tools,calls,initialize,dispose};
}
test('hydration registers exactly one discoverable public collaboration tool',async()=>{
  let finish;const f=await fixture({ready:new Promise(resolve=>finish=resolve)});assert.equal(f.tools.length,0);finish();await f.initialize;
  assert.deepEqual(f.tools.map(t=>t.name),['collaboration']);
  const tool=f.tools[0];
  assert.deepEqual(tool.parameters,collaborationSchema.parameters);
  assert.equal(tool.parameters.additionalProperties,false);
  assert.deepEqual(tool.parameters.required,['action']);
  assert.match(tool.description,/unloaded sessions/);
  assert.match(tool.description,/archive refuses observed activity/);
  assert.equal((await tool.execute({action:'create',workspaceId:'project'},{})).action,'create');
  assert.equal(f.events.has('agent/created'),false);assert.equal(f.events.has('dispose'),false);await f.dispose();assert.deepEqual(f.calls.slice(-4),['api-dispose','many-dispose','lifecycle-dispose','domain-close']);
});
test('natural step returns exact decision and isolates notification/storage failures',async()=>{
  const f=await fixture({onLive:async()=>{throw new Error('storage offline');}});await f.initialize;
  const decision={kind:'enter',messages:[],startsRequestSeries:true},next=async()=>decision;
  assert.equal(await f.events.get('agent/pre-step')({agent:{id:'synthetic'},signal:new AbortController().signal},next),decision);
  assert.equal(f.calls.filter(x=>x==='live').length,1);
  const reject={kind:'reject'};assert.equal(await f.events.get('agent/pre-step')({agent:{}},async()=>reject),reject);assert.equal(f.calls.filter(x=>x==='live').length,1);
  await assert.rejects(f.events.get('agent/pre-step')({agent:{}},async()=>{throw new Error('native rejection');}),/native rejection/);
  f.events.get('agent/disposed')({agent:{id:'synthetic'}});assert.ok(f.calls.includes('agent-disposed'));assert.equal(f.events.has('dispose'),false);await f.dispose();
});
test('owned unload waits module drain before closing domain, without dispose event',async()=>{
  const drain=deferred(),f=await fixture({drain:drain.promise});await f.initialize;
  const disposal=f.dispose();await Promise.resolve();await Promise.resolve();
  assert.ok(f.calls.includes('api-dispose'));assert.ok(!f.calls.includes('domain-close'));
  drain.resolve();await disposal;assert.equal(f.calls.at(-1),'domain-close');assert.equal(f.tools.length,0);assert.equal(f.events.size,0);
});
test('unload during late domain acquisition closes acquired handle exactly once',async()=>{
  const open=deferred(),f=await fixture({open:open.promise});const disposal=f.dispose();
  open.resolve();await assert.rejects(f.initialize,/inactive effect/);await disposal;
  assert.equal(f.calls.filter(x=>x==='domain-close').length,1);assert.equal(f.tools.length,0);
});
test('unload during hydration drains and closes without registering tools',async()=>{
  const ready=deferred(),f=await fixture({ready:ready.promise});await Promise.resolve();const disposal=f.dispose();
  ready.resolve();await assert.rejects(f.initialize,/inactive effect/);await disposal;
  assert.equal(f.calls.filter(x=>x==='domain-close').length,1);assert.equal(f.tools.length,0);
});
test('failed hydration, construction and registration close domain exactly once',async()=>{
  for(const options of [{ready:Promise.resolve().then(()=>{throw new Error('hydrate failed');})},{failCreate:true},{failRegister:true}]) {
    options.ready?.catch(()=>{});const f=await fixture(options);await assert.rejects(f.initialize,/failed/);await f.dispose();
    assert.equal(f.calls.filter(x=>x==='domain-close').length,1);assert.equal(f.tools.length,0);
  }
});
test('synchronous module disposal failure cannot skip sibling drain or domain close',async()=>{
  const f=await fixture({failDispose:true});await f.initialize;await f.dispose();
  assert.deepEqual(f.calls.slice(-4),['api-dispose','many-dispose','lifecycle-dispose','domain-close']);
});
