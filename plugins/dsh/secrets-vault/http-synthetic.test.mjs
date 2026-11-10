import test from 'node:test';
import assert from 'node:assert/strict';
import {httpOperation} from './operations.js';
// Replace fetch: never network, subprocesses, real credentials or Vault state.
const metadata={kind:'token',allowAgentUse:true,url:'https://synthetic.invalid/'};
const secret={token:'SYNTHETIC-TOKEN'};
test('HTTP combines caller abort and fixed deadline, uses manual redirects and caps response body',async t=>{
 let options,cancelled=false;
 t.mock.method(globalThis,'fetch',async(_url,init)=>{options=init;return {status:200,body:new ReadableStream({start(controller){controller.enqueue(Buffer.alloc(40000,97));controller.enqueue(Buffer.alloc(40000,98));},cancel(){cancelled=true;}})};});
 let deadline;
 t.mock.method(AbortSignal,'timeout',ms=>{deadline=ms;return new AbortController().signal;});
 const controller=new AbortController();
 const result=await httpOperation(metadata,secret,{url:metadata.url},controller.signal);
 assert.equal(deadline,30000);assert.equal(options.redirect,'manual');assert.equal(result.truncated,true);assert.ok(Buffer.byteLength(result.body)<=65536);assert.equal(cancelled,true);
 controller.abort();assert.equal(options.signal.aborted,true);assert.equal(result.headers,undefined);
});
test('HTTP response streaming propagates abort instead of continuing to collect',async t=>{
 const controller=new AbortController();let pending;
 t.mock.method(globalThis,'fetch',async(_url,init)=>({status:200,body:new ReadableStream({start(stream){init.signal.addEventListener('abort',()=>stream.error(init.signal.reason),{once:true});pending=true;}})}));
 const result=httpOperation(metadata,secret,{url:metadata.url},controller.signal);
 await Promise.resolve();assert.equal(pending,true);controller.abort();await assert.rejects(result,{name:'AbortError'});
});
