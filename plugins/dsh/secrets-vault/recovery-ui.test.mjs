import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';

// Source-only VM harness. No real network, browser, vault, clipboard, or secrets.
const source=await readFile(new URL('./client.js',import.meta.url),'utf8');
function fixture({failRefresh=false,dropIssuance=false,issuanceGate}={}) {
  let hook=null, api,poll,interval;
  const React={
    createElement:(type,props,...children)=>({type,props:props||{},children}),
    Fragment:Symbol('Fragment'),
    useState:initial=>hook.state(initial),
    useEffect:fn=>hook.effects.push(fn),
    useSyncExternalStore:(_subscribe,get)=>get(),
  };
  const calls=[];
  const sandbox={window:{__ModuleLoader__:{load:module=>{api=module.factory(name=>{assert.equal(name,'react');return React;});}}},URL,document:{baseURI:'https://synthetic.invalid/'},setInterval:(fn,ms)=>{poll=fn;interval=ms;return 1;},clearInterval:()=>{},fetch:async(_url,options)=>{
    const args=JSON.parse(options.body);calls.push(args);
    if(['setup','enableRecovery','rotateRecovery','recover'].includes(args.op))await issuanceGate;
    if(args.op==='status'&&failRefresh)throw new Error('synthetic dropped status');
    if(dropIssuance&&['setup','enableRecovery','rotateRecovery','recover'].includes(args.op))throw new Error('synthetic lost issuance response');
    const data=args.op==='status'?{initialized:true,unlocked:true,recoveryAvailable:true}:args.op==='list'?{records:[]}:['setup','enableRecovery','rotateRecovery','recover'].includes(args.op)?{recoveryKey:'SYNTHETIC-RECOVERY-KEY'}:{};
    return {ok:true,json:async()=>({ok:true,...data})};
  }};
  const instrumented=source.replace("    return {\n      inject:['slots','locale'],","    return {controllerFor,PasswordForm,RecoveryIssued,Modal,\n      inject:['slots','locale'],");
  assert.notEqual(instrumented,source);
  vm.runInNewContext(instrumented,sandbox);
  function component(fn,props,initial=[]) {
    const values=[...initial];
    return {render(){let index=0;const effects=[];hook={effects,state(value){const current=index++;if(!(current in values))values[current]=typeof value==='function'?value():value;return [values[current],next=>{values[current]=typeof next==='function'?next(values[current]):next;}];}};const tree=fn(props);hook=null;for(const effect of effects)effect();return tree;}};
  }
  return {...api,calls,component,poll:()=>poll(),interval:()=>interval};
}
function descendants(tree,predicate){if(!tree||typeof tree!=='object')return [];return [...(predicate(tree)?[tree]:[]),...(tree.children||[]).flat(Infinity).flatMap(child=>descendants(child,predicate))];}
const t=key=>key;

test('idle polling is status-only at two seconds, never full-catalog refresh',async()=>{
 const f=fixture(),controller=f.controllerFor(t),unmount=controller.mount();
 await new Promise(resolve=>setImmediate(resolve));assert.equal(f.interval(),2000);
 f.calls.length=0;for(let i=0;i<10;i++)await f.poll();
 assert.equal(f.calls.length,10);assert.ok(f.calls.every(call=>call.op==='status'));
 unmount();controller.dispose();
});
test('recovery key stays out of globally observable controller snapshot',()=>{
  const f=fixture(),controller=f.controllerFor(t);
  controller.issueRecovery('SYNTHETIC-RECOVERY-KEY');
  assert.equal(controller.getSnapshot().modal.mode,'recoveryIssued');
  assert.equal(JSON.stringify(controller.getSnapshot()).includes('SYNTHETIC-RECOVERY-KEY'),false);
  assert.equal(controller.peekIssuedRecovery(),'SYNTHETIC-RECOVERY-KEY');
  assert.equal(controller.peekIssuedRecovery(),'SYNTHETIC-RECOVERY-KEY');
  controller.acknowledgeRecovery();
  assert.equal(controller.peekIssuedRecovery(),null);
});

test('issuance blocks normal open and close until local acknowledgement',async()=>{
  const f=fixture(),controller=f.controllerFor(t);
  controller.issueRecovery('SYNTHETIC-RECOVERY-KEY');
  controller.close();await controller.open({mode:'add'});
  assert.equal(controller.getSnapshot().modal.mode,'recoveryIssued');
  assert.equal(f.calls.length,0);
  const view=f.component(f.RecoveryIssued,{controller,t,s:controller.getSnapshot()});
  let tree=view.render();tree=view.render();
  assert.equal(descendants(tree,node=>node.type==='textarea')[0].props.value,'SYNTHETIC-RECOVERY-KEY');
  assert.equal(descendants(tree,node=>node.props.primary)[0].props.disabled,true);
  descendants(tree,node=>node.type==='input'&&node.props.type==='checkbox')[0].props.onChange({target:{checked:true}});
  tree=view.render();const done=descendants(tree,node=>node.props.primary)[0];
  assert.equal(done.props.disabled,false);done.props.onClick();
  assert.equal(controller.getSnapshot().modal,null);
});

for(const mode of ['setup','enableRecovery','rotateRecovery','recover'])test(`${mode}: issuance survives subsequent status-refresh network failure`,async()=>{
  const f=fixture({failRefresh:true}),controller=f.controllerFor(t);
  controller.set({initialized:mode!=='setup',unlocked:['enableRecovery','rotateRecovery'].includes(mode),modal:{mode}});
  const s=controller.getSnapshot();
  const form=f.component(f.PasswordForm,{controller,t,s,mode},['synthetic-password-long','synthetic-password-long',false,'synthetic-old-recovery']).render();
  await form.props.onSubmit({preventDefault(){}});
  assert.equal(f.calls[0].op,mode);
  assert.equal(controller.getSnapshot().modal.mode,'recoveryIssued');
  assert.equal(controller.getSnapshot().pending,false);
  assert.equal(controller.peekIssuedRecovery(),'SYNTHETIC-RECOVERY-KEY');
  assert.equal(JSON.stringify(controller.getSnapshot()).includes('SYNTHETIC-RECOVERY-KEY'),false);
});

for(const mode of ['setup','enableRecovery','rotateRecovery','recover'])test(`${mode}: lost issuance response gives uncertain-outcome recovery guidance`,async()=>{
  const f=fixture({dropIssuance:true}),controller=f.controllerFor(t);
  controller.set({initialized:mode!=='setup',unlocked:['enableRecovery','rotateRecovery'].includes(mode),modal:{mode}});
  const form=f.component(f.PasswordForm,{controller,t,s:controller.getSnapshot(),mode},['synthetic-password-long','synthetic-password-long',false,'synthetic-old-recovery']).render();
  await form.props.onSubmit({preventDefault(){}});
  assert.equal(controller.getSnapshot().error,'recoveryFailure');
  assert.equal(controller.peekIssuedRecovery(),null);
  assert.equal(controller.getSnapshot().pending,false);
});

test('lock preserves unacknowledged key but disposal clears it',async()=>{
  const f=fixture(),controller=f.controllerFor(t);controller.issueRecovery('SYNTHETIC-RECOVERY-KEY');
  await controller.lock();
  assert.equal(f.calls[0].op,'lock');
  assert.equal(controller.getSnapshot().modal.mode,'recoveryIssued');
  assert.equal(controller.peekIssuedRecovery(),'SYNTHETIC-RECOVERY-KEY');
  controller.dispose();
  assert.equal(controller.peekIssuedRecovery(),null);
});

for(const mode of ['setup','enableRecovery','rotateRecovery','recover'])test(`${mode}: late issuance after disposal cannot retain or publish the key`,async()=>{
 let release;const f=fixture({issuanceGate:new Promise(r=>release=r)}),controller=f.controllerFor(t);
 controller.set({initialized:mode!=='setup',unlocked:true,modal:{mode}});
 const form=f.component(f.PasswordForm,{controller,t,s:controller.getSnapshot(),mode},['synthetic-password-long','synthetic-password-long',false,'synthetic-old']).render();
 const pending=form.props.onSubmit({preventDefault(){}});assert.equal(f.calls[0].op,mode);
 controller.dispose();let publications=0;controller.subscribe(()=>publications++);release();await pending;
 assert.equal(controller.peekIssuedRecovery(),null);assert.equal(controller.getSnapshot().modal,null);assert.equal(publications,0);
 assert.equal(f.calls.length,1);
});
test('empty issued key never permits acknowledgement',()=>{
  const f=fixture(),controller=f.controllerFor(t);controller.issueRecovery(null);
  const view=f.component(f.RecoveryIssued,{controller,t,s:controller.getSnapshot()});
  let tree=view.render();descendants(tree,node=>node.type==='input')[0].props.onChange({target:{checked:true}});
  tree=view.render();assert.equal(descendants(tree,node=>node.props.primary)[0].props.disabled,true);
});

test('Modal resolves setup, locked unlock, recover, and issued transitions',()=>{
  const f=fixture(),controller=f.controllerFor(t);
  const mode=patch=>{controller.set(patch);return f.component(f.Modal,{controller,t}).render().props.mode;};
  assert.equal(mode({initialized:false,modal:{mode:'unlock'}}),'setup');
  assert.equal(mode({initialized:true,unlocked:false,modal:{mode:'add'}}),'unlock');
  assert.equal(mode({modal:{mode:'recover'}}),'recover');
  assert.equal(mode({initialized:false,modal:{mode:'recoveryIssued'}}),'recoveryIssued');
  assert.equal(mode({initialized:true,unlocked:true,modal:{mode:'rotateRecovery'}}),'rotateRecovery');
});

test('remount preserves unacknowledged recovery key',()=>{
  const f=fixture(),controller=f.controllerFor(t);controller.issueRecovery('SYNTHETIC-RECOVERY-KEY');
  const props={controller,t,s:controller.getSnapshot()};
  const first=f.component(f.RecoveryIssued,props);first.render();
  assert.equal(descendants(first.render(),node=>node.type==='textarea')[0].props.value,'SYNTHETIC-RECOVERY-KEY');
  const remount=f.component(f.RecoveryIssued,props);remount.render();
  assert.equal(descendants(remount.render(),node=>node.type==='textarea')[0].props.value,'SYNTHETIC-RECOVERY-KEY');
});
