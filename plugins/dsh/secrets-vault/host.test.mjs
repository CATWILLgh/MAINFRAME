import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {apply} from './index.js';
test('tool access requests dialog, has no secret input, user grants remain private',async()=>{
 const profile=await mkdtemp(path.join(os.tmpdir(),'vault-host-synthetic-'));
 const peer={};let route,tool,dispose;
 const ctx={effect:f=>f(),on:(e,f)=>{if(e==='dispose')dispose=f;},connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:r=>{route=r;return ()=>{};}}},tools:{register:t=>{tool=t;return ()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
 apply(ctx,{profileDirectory:profile,python:fileURLToPath(new URL('./.venv-homebrew/bin/python3',import.meta.url))});
 const ui=async body=>(await route.fetch(new Request('http://localhost/api/secrets-vault/ui',{method:'POST',headers:{'content-type':'application/json','x-secrets-vault-ui':'1'},body:JSON.stringify(body)}))).json();
 try {
  assert(!Object.keys(tool.parameters.properties).some(k=>/secret|password|token|privateKey/.test(k)));
  const locked=await tool.execute({action:'list'},{});assert.equal(locked.code,'VAULT_LOCKED');
  let state=await ui({op:'status'});assert.equal(state.pendingRequest.mode,'unlock');
  assert.equal((await ui({op:'setup',password:'Synthetic-testing-password',confirmation:'Synthetic-testing-password'})).ok,true);
  state=await ui({op:'status'});assert.equal(state.pendingRequest,null);
  const entry=await ui({op:'save',record:{name:'Test',kind:'token',url:'https://example.com',allowAgentUse:true,secret:{token:'synthetic-test-token'}}});
  const updated=await tool.execute({action:'update_metadata',id:entry.id,name:'Updated',url:'https://evil.example',description:'Clarified'},{});assert.equal(updated.id,entry.id);
  const list=await tool.execute({action:'list'},{});assert.equal(list.records[0].name,'Updated');assert.equal(list.records[0].url,'https://example.com');assert.equal(list.records[0].allowAgentUse,true);assert(!JSON.stringify(list).includes('synthetic-test-token'));
  const prepared=await tool.execute({action:'prepare',name:'Prefilled',kind:'password'},{});assert.equal(prepared.prepared,true);
  state=await ui({op:'status'});assert.equal(state.pendingRequest.mode,'add');
  ctx.connection.admit=()=>({peer:{}});
  const response=await route.fetch(new Request('http://localhost/api/secrets-vault/ui',{method:'POST'}));assert.equal(response.status,403);
 } finally {await dispose();}
});
