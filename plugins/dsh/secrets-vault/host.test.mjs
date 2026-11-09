import test from 'node:test';
import {ownedEffects} from './test-effects.mjs';
import assert from 'node:assert/strict';
import {mkdtemp,rm,mkdir,readdir,copyFile,symlink,realpath,cp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

test('native pnpm package resolves profile without environment or source checkout', async t => {
 const root=await mkdtemp(path.join(os.tmpdir(),'vault-native-profile-'));
 const previous=process.env.DSH_PROFILE_DIR;
 delete process.env.DSH_PROFILE_DIR;
 t.after(async()=>{if(previous===undefined)delete process.env.DSH_PROFILE_DIR;else process.env.DSH_PROFILE_DIR=previous;assert.ok(root.startsWith(path.join(os.tmpdir(),'vault-native-profile-')));await rm(root,{recursive:true});});
 const installed=path.join(root,'node_modules','.pnpm','synthetic-package','node_modules','@mainframe','secrets-vault');
 await mkdir(installed,{recursive:true});
 const source=fileURLToPath(new URL('.',import.meta.url));
 for(const name of await readdir(source))if(name.endsWith('.js')||name==='package.json')await copyFile(path.join(source,name),path.join(installed,name));
 await cp(path.join(source,'core'),path.join(installed,'core'),{recursive:true});
 await mkdir(path.join(root,'node_modules','@mainframe'),{recursive:true});
 await symlink(installed,path.join(root,'node_modules','@mainframe','secrets-vault'));
 const copied=await import(pathToFileURL(path.join(installed,'index.js')));
 const {VaultStore:CopiedStore}=await import(pathToFileURL(path.join(installed,'vault-store.js')));
 const {RecoveryStore:CopiedRecovery}=await import(pathToFileURL(path.join(installed,'recovery-store.js')));
 const observed=[];
 CopiedStore.prototype.status=async function(){observed.push(this.databasePath);return {exists:false,unlocked:false};};
 CopiedRecovery.prototype.status=async()=>({exists:false,unlocked:false,recoveryAvailable:false});
 let tool;const {effect,on,dispose}=ownedEffects();
 const ctx={effect,on,connection:{fetch:{register:()=>()=>{}}},tools:{register:value=>{tool=value;return ()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
 try {copied.apply(ctx);await tool.execute({action:'status'},{});assert.equal(observed.at(-1),path.join(await realpath(root),'secrets-vault','vault.v2.json'));}
 finally {await dispose?.();}
 await rm(path.join(root,'node_modules','@mainframe','secrets-vault'));
 await symlink(root,path.join(root,'node_modules','@mainframe','secrets-vault'));
 assert.throws(()=>copied.apply(ctx),/requires a profile directory/);
});
import {apply} from './index.js';
import {VaultStore} from './vault-store.js';
import {RecoveryStore} from './recovery-store.js';

// Intercept the storage boundary: these tests never read a real vault.
test('Node backend resolves profiles and rejects obsolete Python overrides', async t => {
 const previousProfile = process.env.DSH_PROFILE_DIR;
 const previousStatus = VaultStore.prototype.status;
 const previousRecoveryStatus = RecoveryStore.prototype.status;
 RecoveryStore.prototype.status = async () => ({exists:false,unlocked:false,recoveryAvailable:false});
 const observed = [];
 VaultStore.prototype.status = async function () {
  observed.push({databasePath:this.databasePath});
  return {exists:false,unlocked:false};
 };
 t.after(() => {
  VaultStore.prototype.status = previousStatus;
  RecoveryStore.prototype.status = previousRecoveryStatus;
  if(previousProfile === undefined) delete process.env.DSH_PROFILE_DIR;
  else process.env.DSH_PROFILE_DIR = previousProfile;
 });
 function fixture(config) {
  let tool;const {effect,on,dispose}=ownedEffects();
  const ctx = {
   effect,on,
   connection:{fetch:{register:()=>()=>{}}},
   tools:{register:value=>{tool=value;return ()=>{};}},
   systemPrompt:{section:()=>()=>{}}, agents:{get:()=>undefined},
  };
  apply(ctx,config);
  return {tool,dispose};
 }
 const environmentProfile = path.join(os.tmpdir(),'synthetic-vault-environment-profile');
 const explicitProfile = path.join(os.tmpdir(),'synthetic-vault-explicit-profile');
 process.env.DSH_PROFILE_DIR = environmentProfile;
 let instance = fixture();
 try {
  assert.equal((await instance.tool.execute({action:'status'},{})).initialized,false);
  assert.deepEqual(observed.at(-1),{
   databasePath:path.join(environmentProfile,'secrets-vault','vault.v2.json'),
  });
 } finally {await instance.dispose();}
 assert.throws(()=>fixture({profileDirectory:explicitProfile,python:'/obsolete-python'}),/obsolete.*python/i);
 delete process.env.DSH_PROFILE_DIR;
 assert.throws(()=>fixture(),/requires a profile directory/);
 instance = fixture({profileDirectory:explicitProfile});
 try {
  await instance.tool.execute({action:'status'},{});
  assert.equal(observed.at(-1).databasePath,path.join(explicitProfile,'secrets-vault','vault.v2.json'));
 } finally {await instance.dispose();}
});
test('tool access requests dialog, has no secret input, user grants remain private',async()=>{
 const profile=await mkdtemp(path.join(os.tmpdir(),'vault-host-synthetic-'));
 const peer={};let route,tool;const {effect,on,dispose}=ownedEffects();
 const ctx={effect,on,connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:r=>{route=r;return ()=>{};}}},tools:{register:t=>{tool=t;return ()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
 apply(ctx,{profileDirectory:profile});
 const ui=async body=>(await route.fetch(new Request('http://localhost/api/secrets-vault/ui',{method:'POST',headers:{'content-type':'application/json','x-secrets-vault-ui':'1'},body:JSON.stringify(body)}))).json();
 try {
  assert(!Object.keys(tool.parameters.properties).some(k=>/secret|password|token|privateKey/.test(k)));
  const locked=await tool.execute({action:'list'},{});assert.equal(locked.code,'VAULT_LOCKED');
  let state=await ui({op:'status'});assert.equal(state.pendingRequest.mode,'unlock');
  assert.equal((await ui({op:'setup',password:'Synthetic-testing-password',confirmation:'Synthetic-testing-password'})).ok,true);
  state=await ui({op:'status'});assert.equal(state.pendingRequest,null);
  const entry=await ui({op:'save',record:{name:'Test',kind:'token',url:'https://example.com',allowAgentUse:true,secret:{token:'synthetic-test-token'}}});
  assert.equal(entry.ok,true,JSON.stringify(entry));
  const denied=await tool.execute({action:'update_metadata',id:entry.id,name:'Updated',url:'https://evil.example',description:'Clarified'},{});assert.equal(denied.error.code,'VAULT_INVALID_ARGUMENTS');
   const updated=await tool.execute({action:'update_metadata',id:entry.id,name:'Updated',description:'Clarified'},{});assert.equal(updated.id,entry.id);
  const list=await tool.execute({action:'list'},{});assert.equal(list.records[0].name,'Updated');assert.equal(list.records[0].url,'https://example.com');assert.equal(list.records[0].allowAgentUse,true);assert(!JSON.stringify(list).includes('synthetic-test-token'));
  // Two browser views read the same revision. Only the first edit may commit.
  const stale=(await ui({op:'list'})).records[0];
  assert.equal((await ui({op:'updateMetadata',id:stale.id,revision:stale.revision,metadata:{...stale,name:'First view'}})).ok,true);
  for (const body of [
   {op:'updateMetadata',id:stale.id,revision:stale.revision,metadata:{...stale,name:'Stale view'}},
   {op:'delete',id:stale.id,revision:stale.revision},
   {op:'save',record:{...stale,name:'Stale overwrite',secret:{token:'synthetic-stale-token'}}},
  ]) {
   const rejected=await ui(body);assert.equal(rejected.ok,false);assert.equal(rejected.error.code,'VAULT_CONFLICT');
  }
  const fresh=(await ui({op:'list'})).records[0];assert.equal(fresh.name,'First view');
  assert.equal(fresh.revision,stale.revision+1);
  assert.equal((await ui({op:'delete',id:fresh.id,revision:fresh.revision})).ok,true);
  const prepared=await tool.execute({action:'prepare',name:'Prefilled',kind:'password'},{});assert.equal(prepared.prepared,true);
  state=await ui({op:'status'});assert.equal(state.pendingRequest.mode,'add');
  ctx.connection.admit=()=>({peer:{}});
  const response=await route.fetch(new Request('http://localhost/api/secrets-vault/ui',{method:'POST'}));assert.equal(response.status,403);
 } finally {
  await dispose();
  assert.equal(path.dirname(path.resolve(profile)),path.resolve(os.tmpdir()));
  assert.ok(path.basename(profile).startsWith('vault-host-synthetic-'));
  await rm(profile,{recursive:true});
 }
});
