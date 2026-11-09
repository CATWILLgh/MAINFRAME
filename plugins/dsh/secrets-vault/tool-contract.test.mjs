import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import path from 'node:path';
import {readFile} from 'node:fs/promises';
import {ownedEffects} from './test-effects.mjs';

// Pure Host fixture; no clipboard, network, process or credential store access.
async function fixture({httpOperation=async()=>({status:200})}={}) {
 const source=(await readFile(new URL('./index.js',import.meta.url),'utf8')).split('export const inject')[1];
 const owner=ownedEffects(),peer={},calls=[],notifications=[];let tool,route;
 const rows=Array.from({length:105},(_,i)=>({id:String(i),metadata:{name:`Synthetic ${i}`,kind:'token',allowAgentUse:true,url:'https://synthetic.invalid/',tags:['fixture']},revision:1,updated:String(i),created:String(i)}));
 const store={status:async()=>({exists:true,unlocked:true}),list:async()=>{calls.push('list');return rows;},listPage:async options=>{calls.push(['page',options]);return {records:rows.slice(options.offset||0,(options.offset||0)+(options.limit||100)),total:105,nextOffset:(options.offset||0)+(options.limit||100)<105?(options.offset||0)+(options.limit||100):null};},getMetadata:async id=>{calls.push('metadata');return rows.find(r=>r.id===id);},internalGet:async()=>{calls.push('secret');return {token:'SYNTHETIC-SECRET'};},save:async()=>({id:'saved'}),updateMetadata:async()=>({id:'updated'}),dispose:async()=>{}};
 const ctx={...owner,connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:value=>{route=value;return()=>{};}}},tools:{register:value=>{tool=value;return()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:id=>({inject:message=>notifications.push({id,message})})}};
 vm.runInNewContext('const inject'+source.replace(/export /g,'')+';apply(ctx,{profileDirectory:"/synthetic-unused"});',{ctx,path,process:{env:{}},Response,URL,Buffer,VaultStore:class{constructor(){return store;}},RecoveryStore:class{status(){return {}; }},httpOperation,sshOperation:async()=>({exitCode:0}),importClipboard:async()=>({id:'saved'})});
 const ui=async args=>(await route.fetch(new Request('http://synthetic.invalid/api/secrets-vault/ui',{method:'POST',headers:{'x-secrets-vault-ui':'1','content-type':'application/json'},body:JSON.stringify(args)}))).json();
 return {tool,calls,ui,notifications,dispose:owner.dispose};
}
test('discovery delegates bounded paging and metadata lookups avoid full catalog clones',async()=>{
 const f=await fixture();
 const page=await f.tool.execute({action:'list',offset:100,limit:5,query:'Synthetic'},{});
 assert.equal(page.records.length,5);assert.equal(page.records[0].id,'100');assert.equal(page.nextOffset,null);assert.equal(page.total,105);
 assert.equal(JSON.stringify(page).includes('SYNTHETIC-SECRET'),false);
 await f.tool.execute({action:'http',id:'0',url:'https://synthetic.invalid/'},{});
 assert.equal(f.calls.includes('list'),false);assert.ok(f.calls.includes('metadata'));await f.dispose();
});
test('prepare carries only trusted calling agent id to optional metadata notification',async()=>{
 const f=await fixture();
 await f.tool.execute({action:'prepare',name:'Prepared',kind:'password'},{agent:{id:'trusted-session'}});
 const state=await f.ui({op:'status'});assert.equal(state.pendingRequest.sessionId,'trusted-session');
 await f.ui({op:'save',sessionId:state.pendingRequest.sessionId,record:{...state.pendingDraft,secret:{password:'synthetic-private'}}});
 assert.equal(f.notifications[0].id,'trusted-session');assert.equal(JSON.stringify(f.notifications).includes('synthetic-private'),false);
 await f.tool.execute({action:'prepare'},{});assert.equal((await f.ui({op:'status'})).pendingRequest.sessionId,undefined);
 await f.dispose();
});
test('shared Host queue blocks metadata behind remote use and releases it after caller abort',async()=>{
 let started,release;const entered=new Promise(resolve=>{started=resolve;});
 const f=await fixture({httpOperation:async(_row,_secret,_args,signal)=>{started();await new Promise((resolve,reject)=>{release=resolve;signal.addEventListener('abort',()=>reject(signal.reason),{once:true});});return {status:200};}});
 const controller=new AbortController();const remote=f.tool.execute({action:'http',id:'0',url:'https://synthetic.invalid/'},{signal:controller.signal});
 await entered;let finished=false;const list=f.tool.execute({action:'list'},{}).then(value=>{finished=true;return value;});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(finished,false);assert.equal(f.calls.some(x=>Array.isArray(x)&&x[0]==='page'),false);
 controller.abort();await assert.rejects(remote,{name:'AbortError'});assert.equal((await list).records.length,100);release();await f.dispose();
});
test('closed eight-action contract rejects malformed and action-inapplicable fields before effects',async()=>{
 const f=await fixture();assert.equal(f.tool.parameters.additionalProperties,false);assert.equal(f.tool.parameters.properties.action.enum.length,8);
 for(const args of [
  null,[],{}, {action:'toString'},
  {action:'http'},{action:'http',id:'0',url:'http://synthetic.invalid'},
  {action:'http',id:'0',url:'https://elsewhere.invalid'},
  {action:'http',id:'0',url:'https://synthetic.invalid',body:'x'.repeat(65537)},
  {action:'ssh',id:'0'},{action:'ssh',id:'0',command:'x'.repeat(16385)},
  {action:'update_metadata',id:'0',url:'https://unapproved.invalid'},
  {action:'prepare',port:0},{action:'prepare',port:65536},{action:'prepare',port:1.5},
  {action:'prepare',sessionId:'forged-session'},{action:'status',id:'0'},
  {action:'list',offset:-1},{action:'list',limit:101},{action:'list',limit:0},{action:'list',offset:1.5},{action:'list',query:'x'.repeat(257)},
 ]) {
  f.calls.length=0;const result=await f.tool.execute(args,{});
  assert.equal(result.ok,false,JSON.stringify(args));assert.match(result.error.code,/^VAULT_(INVALID_ARGUMENTS|SCOPE_DENIED)$/);
  assert.equal(f.calls.includes('secret'),false);
 }
 const missing=await f.tool.execute({action:'http',id:'absent',url:'https://synthetic.invalid/'},{});assert.equal(missing.error.code,'VAULT_NOT_FOUND');
 await f.dispose();
});
