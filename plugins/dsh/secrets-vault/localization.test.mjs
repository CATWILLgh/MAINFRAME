import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs/promises';
import { buildClient } from './build-client.mjs';

const text = name => fs.readFile(new URL(name, import.meta.url), 'utf8');
const en = JSON.parse(await text('locale/en.json')).ui;
const ru = JSON.parse(await text('locale/ru.json')).ui;
const source = await text('client.js');
function fixture({code,network=false}={}) {
  let api, hook;
  const commands=[],slots=[],cleanups=[],subscriptions=new Set(),dictionaries=new Map();
  let snapshot={active:'en',locales:[{id:'en'},{id:'ru'},{id:'fr'}],revision:0};
  const notify=()=>{snapshot={...snapshot,revision:snapshot.revision+1};for(const fn of subscriptions)fn();};
  const locale={getSnapshot:()=>snapshot,subscribe:fn=>{subscriptions.add(fn);return()=>subscriptions.delete(fn);},register(ns,id,dict){dictionaries.set(id,dict);notify();return()=>{dictionaries.delete(id);notify();};},bind:()=>key=>(dictionaries.get(snapshot.active)||dictionaries.get('ru'))?.[key]||key};
  const React={createElement:(type,props,...children)=>({type,props:props||{},children}),Fragment:Symbol('Fragment'),useEffect:()=>{},useRef:()=>({current:null}),useState:value=>hook(value),useSyncExternalStore:(_subscribe,get)=>get()};
  const instrumented=source.replace("    return {\n      inject:['slots','locale'],","    return {controllerFor,Catalog,Dialog,PasswordForm,RecoveryIssued,\n      inject:['slots','locale'],");
  assert.notEqual(instrumented,source);
  vm.runInNewContext(instrumented,{window:{__ModuleLoader__:{load:module=>{api=module.factory(()=>React);}}},document:{baseURI:'https://synthetic.invalid/'},URL,setInterval:()=>1,clearInterval:()=>{},fetch:async()=>{if(network)throw new Error('untrusted network detail');return{ok:false,json:async()=>({ok:false,error:{code,message:'UNTRUSTED HOST MESSAGE'}})};}});
  const commandUi={register(options){const item={options,disposed:false};commands.push(item);return()=>{item.disposed=true;};}};
  const ctx={locale,effect:fn=>{const cleanup=fn();if(cleanup)cleanups.push(cleanup);},slots:{inject:(_name,fn)=>fn(),register:(options,component)=>{slots.push({options,component});return()=>{};}},inject:(_names,fn)=>fn({commandUi,effect:fn=>{const cleanup=fn();if(cleanup)cleanups.push(cleanup);}})};
  api.apply(ctx);
  return{...api,commands,slots,locale,change(active){snapshot={...snapshot,active};notify();},addLocale(id){snapshot={...snapshot,locales:[...snapshot.locales,{id}]};notify();},render(fn,props,values=[]){let index=0;hook=initial=>{const i=index++;if(!(i in values))values[i]=typeof initial==='function'?initial():initial;return[values[i],next=>{values[i]=typeof next==='function'?next(values[i]):next;}];};return fn(props);},dispose(){for(const fn of cleanups.reverse())fn();assert.equal(subscriptions.size,0);}};
}
function strings(tree){if(typeof tree==='string')return[tree];if(!tree||typeof tree!=='object')return[];return(tree.children||[]).flat(Infinity).flatMap(strings);}

test('Vault artifact embeds exact centralized dictionaries and has no runtime locale imports',async()=>{
  assert.equal(source,await buildClient());
  assert.deepEqual(Object.keys(en).sort(),Object.keys(ru).sort());
  assert.ok(Object.keys(en).length>80);
  for(const [key,value] of Object.entries(ru)){assert.ok(/[А-Яа-яЁё]/u.test(value),key);assert.notEqual(value,en[key],key);}
  const template=await text('client.template.js');
  assert.match(template,/registerMainframeLocale\(ctx.locale,NS,en,ru\)/);
  assert.doesNotMatch(template,/inject:\(\)=>\(\{controller,t\}\)/);
  assert.doesNotMatch(source,/fetch\([^\n]*locale|require\(['"](?:\.\/)?locale|\/\* LOCALE_DICTIONARIES \*\//);
});

test('native locale selection updates command copy and English overrides external Russian fallback',()=>{
  const f=fixture();
  assert.equal(f.commands.at(-1).options.label(),en.panel);
  f.change('ru');
  assert.equal(f.commands.at(-1).options.label(),ru.panel);
  assert.equal(f.commands.at(-1).options.description(),ru.commandDescription);
  assert.equal(f.commands[0].disposed,true);
  f.change('fr');assert.equal(f.commands.at(-1).options.label(),en.panel);
  f.addLocale('external-russian-fallback');f.change('external-russian-fallback');
  assert.equal(f.commands.at(-1).options.description(),en.commandDescription);
  assert.equal(f.locale.bind('secretsVault')('unlock'),en.unlock);
  f.dispose();assert.equal(f.commands.at(-1).disposed,true);
});

test('stored network and API error keys retranslate without exposing raw host errors',async()=>{
  for(const [options,key] of [[{network:true},'networkError'],[{code:'VAULT_CONFLICT'},'conflictError'],[{code:'LEGACY_VAULT_FORMAT'},'legacyError'],[{code:'VAULT_BUSY'},'busyError'],[{code:'VAULT_UNCERTAIN_COMMIT'},'uncertainError'],[{code:'VAULT_EXTERNAL_CHANGE'},'externalError'],[{code:'VAULT_DISPOSED'},'closedError'],[{code:'VAULT_OWNERSHIP_LOST'},'ownershipError'],[{code:'UNSAFE_VAULT_PATH'},'unsafePathError'],[{code:'UNKNOWN'},'requestError']]){
    const f=fixture(options),controller=f.controllerFor();
    await controller.run(()=>controller.request('status'));
    assert.equal(controller.getSnapshot().error,key);
    const props={controller,t:f.locale.bind('secretsVault')};
    assert.ok(strings(f.render(f.Catalog,props)).includes(en[key]));
    f.change('ru');assert.ok(strings(f.render(f.Catalog,props)).includes(ru[key]));
    assert.doesNotMatch(JSON.stringify(controller.getSnapshot()),/UNTRUSTED|untrusted/);
    f.dispose();
  }
});

test('open password and recovery forms retranslate without clearing private inputs or changing acknowledgement',()=>{
  const f=fixture(),controller=f.controllerFor(),t=f.locale.bind('secretsVault');
  const s={pending:false,modal:{mode:'recover'}};
  const state=['synthetic-master-password','synthetic-master-password',false,'synthetic-recovery-key'];
  assert.ok(strings(f.render(f.PasswordForm,{controller,t,s,mode:'recover'},state)).includes(en.recoveryHelp));
  f.change('ru');
  assert.ok(strings(f.render(f.PasswordForm,{controller,t,s,mode:'recover'},state)).includes(ru.recoveryHelp));
  assert.deepEqual(state,['synthetic-master-password','synthetic-master-password',false,'synthetic-recovery-key']);
  const recoveryState=[false,'synthetic-issued-key'];
  const first=f.render(f.RecoveryIssued,{controller,t,s},recoveryState);
  assert.ok(strings(first).includes(ru.recoveryIssuedHelp));
  f.change('en');assert.ok(strings(f.render(f.RecoveryIssued,{controller,t,s},recoveryState)).includes(en.recoveryIssuedHelp));
  assert.deepEqual(recoveryState,[false,'synthetic-issued-key']);
  for(const dict of [en,ru])for(const key of ['recoveryHelp','recoveryEnableHelp','recoveryIssuedHelp','recoveryBackup','recoveryFailure','legacyError','busyError','uncertainError','externalError'])assert.ok(dict[key].length>40,key);
  f.dispose();
});
