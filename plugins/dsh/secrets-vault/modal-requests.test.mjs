import test from 'node:test';
import {ownedEffects} from './test-effects.mjs';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {apply} from './index.js';

// Disposable storage only; no profile, browser, clipboard, or real secrets.
test('each explicit unlock or prepare request gets a fresh modal request ID',async()=>{
  const profile=await mkdtemp(path.join(os.tmpdir(),'vault-modal-synthetic-'));
  const peer={};let route,tool;const {effect,on,dispose}=ownedEffects();
  const ctx={effect,on,connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:value=>{route=value;return()=>{};}}},tools:{register:value=>{tool=value;return()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
  apply(ctx,{profileDirectory:profile});
  const status=async()=>{
    const response=await route.fetch(new Request('https://synthetic.invalid/api/secrets-vault/ui',{method:'POST',headers:{'content-type':'application/json','x-secrets-vault-ui':'1'},body:JSON.stringify({op:'status'})}));
    const state=await response.json();assert.equal(state.ok,true);return state;
  };
  try {
    for(const action of ['request_access','prepare']){
      const args={action,...(action==='prepare'?{name:'Synthetic draft',kind:'token'}:{})};
      await tool.execute(args,{});const first=await status();
      assert.equal((await status()).pendingRequest.id,first.pendingRequest.id,'polling must not change request identity');
      await tool.execute(args,{});const retry=await status();
      assert.notEqual(retry.pendingRequest.id,first.pendingRequest.id,`${action} retry must reopen a cancelled modal`);
      assert.equal(retry.pendingRequest.mode,action==='prepare'?'add':'unlock');
    }
  } finally {
    await dispose();
    assert.equal(path.dirname(profile),path.resolve(os.tmpdir()));
    assert.ok(path.basename(profile).startsWith('vault-modal-synthetic-'));
    await rm(profile,{recursive:true});
  }
});

for(const filename of ['client.template.js','client.js'])test(`${filename}: cancelling suppresses polling but a fresh explicit request reopens`,async()=>{
  const source=await readFile(new URL(filename,import.meta.url),'utf8');
  const instrumented=source.replace("    return {\n      inject:['slots','locale'],","    return {controllerFor,\n      inject:['slots','locale'],");
  assert.notEqual(instrumented,source);
  let api,poll,incoming={id:'1',mode:'unlock'};
  const sandbox={window:{__ModuleLoader__:{load:module=>{api=module.factory(()=>({}));}}},URL,document:{baseURI:'https://synthetic.invalid/'},setInterval:fn=>(poll=fn,1),clearInterval:()=>{},fetch:async()=>({ok:true,json:async()=>({ok:true,initialized:true,unlocked:false,pendingRequest:incoming})})};
  vm.runInNewContext(instrumented,sandbox);
  const controller=api.controllerFor();controller.mount();
  try {
    await new Promise(setImmediate);assert.equal(controller.getSnapshot().modal.mode,'unlock');
    controller.close();assert.equal(controller.getSnapshot().modal,null);
    await poll();assert.equal(controller.getSnapshot().modal,null,'polling must respect Cancel');
    incoming={id:'2',mode:'unlock'};
    await poll();assert.equal(controller.getSnapshot().modal.mode,'unlock','explicit retry must reopen');
    controller.close();incoming={id:'3',mode:'add'};
    await poll();assert.equal(controller.getSnapshot().modal.mode,'add');
    controller.close();await poll();assert.equal(controller.getSnapshot().modal,null);
    incoming={id:'4',mode:'add'};
    await poll();assert.equal(controller.getSnapshot().modal.mode,'add','prepare retry must reopen');
  } finally {controller.dispose();}
});
