import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import path from 'node:path';
import {readFile} from 'node:fs/promises';
import {ownedEffects} from './test-effects.mjs';

const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
// VM storage/operation mocks only: no real or temporary store is opened here.
async function fixture({gate,fail,unlocked=false,disposeFailures=0}={}) {
  const original=await readFile(new URL('./index.js',import.meta.url),'utf8');
  const source=original.slice(original.indexOf('export const inject')).replace(/export /g,'');
  const calls=[],owner=ownedEffects(),peer={};let tool,route;
  const ctx={...owner,connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:value=>{if(fail==='route')throw new Error('setup failed');route=value;return()=>calls.push('route-remove');}}},tools:{register:value=>{if(fail==='tool')throw new Error('setup failed');tool=value;return()=>calls.push('tool-remove');}},systemPrompt:{section:()=>{if(fail==='prompt')throw new Error('setup failed');return()=>{};}},agents:{get:()=>undefined}};
  const apply=vm.runInNewContext(source+';apply',{path,process:{env:{}},Response,URL,importClipboard:async()=>{calls.push('clipboard');return {id:'synthetic'};},VaultStore:class {async status(){calls.push('status');await gate;return {exists:false,unlocked};}list(){calls.push('list');return [];}dispose(){calls.push('store-dispose');if(disposeFailures-->0)return Promise.reject(Object.assign(new Error('synthetic I/O'),{code:'EIO'}));}},RecoveryStore:class {constructor(){if(fail==='recovery')throw new Error('setup failed');}status(){return {};}}});
  let failure;try{apply(ctx,{profileDirectory:'/synthetic-not-accessed'});}catch(error){failure=error;}
  return {owner,calls,tool,route,failure};
}
test('owned unload closes admission synchronously, drains transactions and disposes exactly once',async()=>{
  const gate=deferred(),f=await fixture({gate:gate.promise});
  const pending=f.tool.execute({action:'status'},{});await Promise.resolve();
  assert.deepEqual(f.calls,['status']);const disposal=f.owner.dispose();
  await assert.rejects(f.tool.execute({action:'status'},{}),/shutting down/);
  assert.ok(!f.calls.includes('store-dispose'));gate.resolve();await pending;await disposal;await f.owner.dispose();
  assert.equal(f.calls.filter(x=>x==='store-dispose').length,1);assert.equal(f.calls.at(-1),'store-dispose');
});
test('pre-aborted and queued cancelled tool calls never reach storage or clipboard',async()=>{
  const early=await fixture({unlocked:true}),cancel=new AbortController();
  cancel.abort();await assert.rejects(early.tool.execute({action:'save_from_clipboard'},{signal:cancel.signal}),{name:'AbortError'});
  assert.deepEqual(early.calls,[]);await early.owner.dispose();
  const gate=deferred(),f=await fixture({gate:gate.promise,unlocked:true});
  const active=f.tool.execute({action:'status'},{});await Promise.resolve();
  const queuedCancel=new AbortController();const queued=f.tool.execute({action:'save_from_clipboard'},{signal:queuedCancel.signal});
  const rejected=assert.rejects(queued,{name:'AbortError'});queuedCancel.abort();gate.resolve();await active;await rejected;
  assert.deepEqual(f.calls,['status']);await f.owner.dispose();
});
test('single-shot owned cleanup retries transient EIO once and exposes persistent failure',async()=>{
  for(const failures of [1,2]) {
    const f=await fixture({disposeFailures:failures});const disposal=f.owner.dispose();
    if(failures===1)await disposal;else await assert.rejects(disposal,{code:'EIO'});
    assert.equal(f.calls.filter(x=>x==='store-dispose').length,2);
    await assert.rejects(f.tool.execute({action:'status'},{}),/shutting down/);
  }
});
test('late UI body parsing cannot admit work after cleanup',async()=>{
  const f=await fixture(),body=deferred();
  const pending=f.route.fetch({headers:new Headers({'x-secrets-vault-ui':'1','content-type':'application/json'}),text:()=>body.promise});
  await f.owner.dispose();body.resolve('{"op":"status"}');
  assert.equal((await (await pending).json()).ok,false);assert.ok(!f.calls.includes('status'));
});
test('initialization and each registration failure retain early effect cleanup',async()=>{
  for(const fail of ['recovery','route','tool','prompt']) {
    const f=await fixture({fail});assert.match(f.failure.message,/setup failed/);
    await f.owner.dispose();await f.owner.dispose();assert.equal(f.calls.filter(x=>x==='store-dispose').length,1);
  }
});
