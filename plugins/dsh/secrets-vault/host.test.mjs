import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,mkdir,readdir,copyFile,symlink,realpath} from 'node:fs/promises';
import {accessSync,constants} from 'node:fs';
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
 await mkdir(path.join(root,'node_modules','@mainframe'),{recursive:true});
 await symlink(installed,path.join(root,'node_modules','@mainframe','secrets-vault'));
 const copied=await import(pathToFileURL(path.join(installed,'index.js')));
 const {VaultStore:CopiedStore}=await import(pathToFileURL(path.join(installed,'vault-store.js')));
 const {RecoveryStore:CopiedRecovery}=await import(pathToFileURL(path.join(installed,'recovery-store.js')));
 const observed=[];
 CopiedStore.prototype.status=async function(){observed.push(this.databasePath);return {exists:false,unlocked:false};};
 CopiedRecovery.prototype.status=async()=>({exists:false,unlocked:false,recoveryAvailable:false});
 let tool,dispose;
 const ctx={effect:fn=>fn(),on:(event,fn)=>{if(event==='dispose')dispose=fn;},connection:{fetch:{register:()=>()=>{}}},tools:{register:value=>{tool=value;return ()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
 try {copied.apply(ctx);await tool.execute({action:'status'},{});assert.equal(observed.at(-1),path.join(await realpath(root),'secrets-vault','vault.db'));}
 finally {await dispose?.();}
 await rm(path.join(root,'node_modules','@mainframe','secrets-vault'));
 await symlink(root,path.join(root,'node_modules','@mainframe','secrets-vault'));
 assert.throws(()=>copied.apply(ctx),/requires a profile directory/);
});
import {apply} from './index.js';
import {VaultStore} from './vault-store.js';
import {RecoveryStore} from './recovery-store.js';

// Intercept the worker boundary: these tests never spawn Python or read a vault.
// The historical integration test below still requires an external runtime.
test('bundled interpreter defaults to package runtime and profile environment', async t => {
 const previousProfile = process.env.DSH_PROFILE_DIR;
 const previousStatus = VaultStore.prototype.status;
 const previousRecoveryStatus = RecoveryStore.prototype.status;
 RecoveryStore.prototype.status = async () => ({exists:false,unlocked:false,recoveryAvailable:false});
 const observed = [];
 VaultStore.prototype.status = async function () {
  observed.push({python:this.python,databasePath:this.databasePath});
  return {exists:false,unlocked:false};
 };
 t.after(() => {
  VaultStore.prototype.status = previousStatus;
  RecoveryStore.prototype.status = previousRecoveryStatus;
  if(previousProfile === undefined) delete process.env.DSH_PROFILE_DIR;
  else process.env.DSH_PROFILE_DIR = previousProfile;
 });
 function fixture(config) {
  let tool,dispose;
  const ctx = {
   effect:f=>f(), on:(event,fn)=>{if(event==='dispose')dispose=fn;},
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
   python:fileURLToPath(new URL('./runtime/bin/python3.12',import.meta.url)),
   databasePath:path.join(environmentProfile,'secrets-vault','vault.db'),
  });
 } finally {await instance.dispose();}
 const explicitPython = path.join(os.tmpdir(),'synthetic-external-python');
 instance = fixture({profileDirectory:explicitProfile,python:explicitPython});
 try {
  await instance.tool.execute({action:'status'},{});
  assert.deepEqual(observed.at(-1),{
   python:explicitPython,databasePath:path.join(explicitProfile,'secrets-vault','vault.db'),
  });
 } finally {await instance.dispose();}
 delete process.env.DSH_PROFILE_DIR;
 assert.throws(()=>fixture(),/requires a profile directory/);
 instance = fixture({profileDirectory:explicitProfile});
 try {
  await instance.tool.execute({action:'status'},{});
  assert.equal(observed.at(-1).databasePath,path.join(explicitProfile,'secrets-vault','vault.db'));
 } finally {await instance.dispose();}
});
test('tool access requests dialog, has no secret input, user grants remain private',async()=>{
 const python=process.env.MAINFRAME_TEST_VAULT_PYTHON || fileURLToPath(new URL('./runtime/bin/python3.12',import.meta.url));
 try {accessSync(python,constants.X_OK);}
 catch {throw new Error('Vault integration tests require an executable bundled runtime; stage runtime/bin/python3.12 or set MAINFRAME_TEST_VAULT_PYTHON to a verified Python with sqlcipher3.');}
 const profile=await mkdtemp(path.join(os.tmpdir(),'vault-host-synthetic-'));
 const peer={};let route,tool,dispose;
 const ctx={effect:f=>f(),on:(e,f)=>{if(e==='dispose')dispose=f;},connection:{browserPeer:peer,admit:()=>({peer}),fetch:{register:r=>{route=r;return ()=>{};}}},tools:{register:t=>{tool=t;return ()=>{};}},systemPrompt:{section:()=>()=>{}},agents:{get:()=>undefined}};
 apply(ctx,{profileDirectory:profile,python});
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
 } finally {
  await dispose();
  assert.equal(path.dirname(path.resolve(profile)),path.resolve(os.tmpdir()));
  assert.ok(path.basename(profile).startsWith('vault-host-synthetic-'));
  await rm(profile,{recursive:true});
 }
});
