import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import { embedLocaleDictionaries } from '../build-locales.mjs';
const source=await fs.readFile(new URL('client.js',import.meta.url),'utf8');
function harness({storage:sharedStorage,scope='a'.repeat(64)}={}){
  const values=sharedStorage??new Map();const storage={get length(){return values.size;},key:i=>[...values.keys()][i]??null,getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
  let wall=1800000000000,mono=0,focus=true,fail=false,hold=null;
  const calls=[],timers=new Map(),listeners=new Map();let next=0;
  const events=(prefix)=>({addEventListener(name,fn){listeners.set(`${prefix}:${name}`,fn);},removeEventListener(name){listeners.delete(`${prefix}:${name}`);}});
  const window={localStorage:storage,...events('w'),__ModuleLoader__:{load({factory}){factory(()=>({createElement(){}}));}}};
  const document={...events('d'),visibilityState:'visible',hasFocus:()=>focus};
  const context={crypto:{randomUUID:()=>`test-${Math.random()}`},window,document,Date:class extends Date{static now(){return wall;}},performance:{now:()=>mono},AbortController,Intl,console,
    setInterval(fn){const id=++next;timers.set(id,fn);return id;},clearInterval(id){timers.delete(id);},setTimeout(){return ++next;},clearTimeout(){},
    fetch:async(url,options)=>{const body=JSON.parse(options.body);if(body.op==='bootstrap')return {ok:true,json:async()=>({ok:true,queueScope:scope})};calls.push({url,options,body});if(hold)await hold;if(fail)throw new Error('offline');return {ok:true,json:async()=>({ok:true,persistedThrough:wall,trackingSince:1800000000000,userMs:0,agentMs:0})};}
  };
  vm.runInNewContext(source.replace("return {inject:['slots','locale'],apply(ctx){","globalThis.makeController=createController;return {inject:['slots','locale'],apply(ctx){"),context);
  const controller=context.makeController();const dispose=controller.start();
  return {controller,calls,timers,listeners,dispose,setFail:v=>{fail=v;},setHold:v=>{hold=v;},advance(ms){wall+=ms;mono+=ms;},tick(){for(const fn of timers.values())fn();},event(name,e={}){listeners.get(name)?.({type:name.split(':')[1],...e});},setFocus(v){focus=v;},setVisible(v){document.visibilityState=v?'visible':'hidden';}};
}
const turn=()=>new Promise(resolve=>setImmediate(resolve));
test('controller records intervals only, privately syncs and owns all global resources',async()=>{
  const x=harness();assert.equal(x.listeners.size,15);assert.equal(x.controller.getSnapshot().active,true);
  x.advance(5000);x.tick();await x.controller.flush();assert.equal(x.calls.length,1);
  assert.deepEqual(x.calls[0].body,{op:'activity',intervals:[{start:1800000000000,end:1800000005000}]});
  assert.equal(x.calls[0].options.headers['x-activity-analytics-ui'],'1');assert.equal(x.calls[0].url,'/api/activity-analytics/ui');
  x.advance(5000);x.event('w:keydown',{key:'DO-NOT-STORE',target:{value:'PRIVATE-TEXT'}});await x.controller.flush();
  assert.doesNotMatch(JSON.stringify(x.calls),/DO-NOT-STORE|PRIVATE-TEXT/);
  x.dispose();await turn();assert.equal(x.listeners.size,0);assert.equal(x.timers.size,0);
});
test('focus, idle and sleep update recording status and avoid hidden time',async()=>{
  const x=harness();for(let i=0;i<60;i++){x.advance(5000);x.controller.sample();}assert.equal(x.controller.getSnapshot().active,false);
  x.event('w:pointerdown');assert.equal(x.controller.getSnapshot().active,true);
  x.setFocus(false);x.event('w:blur');assert.equal(x.controller.getSnapshot().active,false);
  x.advance(10000);x.controller.sample();await x.controller.flush();
  assert.equal(x.calls.flatMap(c=>c.body.intervals??[]).reduce((n,v)=>n+v.end-v.start,0),300000);
  x.setFocus(true);x.event('w:focus');assert.equal(x.controller.getSnapshot().active,true);
  x.advance(60000);x.tick();assert.equal(x.controller.getSnapshot().active,false);
  x.event('w:focus');assert.equal(x.controller.getSnapshot().active,false);
  x.event('w:keydown');assert.equal(x.controller.getSnapshot().active,true);x.dispose();await turn();
});
test('text input, composition and touch count globally but automatic scroll and synthetic input cannot extend idle',async()=>{
  const x=harness();for(let i=0;i<60;i++){x.advance(5000);x.event('w:scroll');}assert.equal(x.controller.getSnapshot().active,false);
  x.event('w:input',{isTrusted:false});assert.equal(x.controller.getSnapshot().active,false);
  for(const name of ['beforeinput','input','compositionstart','compositionupdate','touchmove']){x.event(`w:${name}`,{isTrusted:true,data:'PRIVATE-IME'});assert.equal(x.controller.getSnapshot().active,true);x.advance(60000);x.controller.sample();assert.equal(x.controller.getSnapshot().active,false);}
  await x.controller.flush();assert.doesNotMatch(JSON.stringify(x.calls),/PRIVATE-IME/);x.dispose();await turn();
});

test('failed sync retries same intervals; successful retry is idempotent and clears warning',async()=>{
  const x=harness();x.setFail(true);x.advance(5000);x.controller.sample();assert.equal(await x.controller.flush(),false);assert.equal(x.controller.getSnapshot().syncError,true);
  x.setFail(false);assert.equal(await x.controller.flush(),true);assert.deepEqual(x.calls[0].body,x.calls[1].body);assert.equal(x.controller.getSnapshot().syncError,false);
  await x.controller.flush();assert.equal(x.calls.length,2);x.dispose();await turn();
});
test('100k frequent input events never drop time and in-flight ACK preserves new tail',async()=>{
  const x=harness();await x.controller.flush();let release;x.setHold(new Promise(r=>{release=r;}));x.advance(1000);x.controller.sample();const request=x.controller.flush();await turn();
  for(let i=0;i<100000;i++){x.advance(1);x.event('w:input',{isTrusted:true});}
  assert.equal(x.controller.getSnapshot().pendingMs,101000);assert.equal(x.controller.getSnapshot().durable,true);
  release();await request;x.setHold(null);assert.equal(x.controller.getSnapshot().pendingMs,100000);await x.controller.flush();
  assert.equal(x.calls.flatMap(c=>c.body.intervals??[]).reduce((s,v)=>s+v.end-v.start,0),101000);
  assert.equal(x.controller.getSnapshot().pendingMs,0);assert.ok(x.controller.getSnapshot().lastSavedAt);x.dispose();await turn();
});
test('offline queue survives a new controller and is isolated by authenticated profile scope',async()=>{
  const storage=new Map(),x=harness({storage});await x.controller.flush();x.setFail(true);x.advance(10000);x.controller.sample();await x.controller.flush();assert.equal(x.controller.getSnapshot().pendingMs,10000);x.dispose();await turn();
  const y=harness({storage,scope:'b'.repeat(64)});await y.controller.flush();assert.equal(y.calls.length,0);y.dispose();await turn();
  const z=harness({storage});z.advance(10000);await z.controller.flush();assert.equal(z.calls[0].body.intervals[0].end-z.calls[0].body.intervals[0].start,10000);assert.equal(z.controller.getSnapshot().pendingMs,0);z.dispose();await turn();
});
test('help popover supports hover, keyboard, pinned click and outside dismissal',()=>{
  const states=[],effects=[],listeners=new Map();let cursor=0;const root={contains:t=>t==='inside'};
  const React={createElement:(type,props,...children)=>({type,props:props??{},children}),useState(initial){const index=cursor++;if(!(index in states))states[index]=initial;return[states[index],value=>{states[index]=value;}];},useRef:()=>({current:root}),useId:()=> 'help-test',useEffect(fn){effects.push(fn);}};
  const context={window:{__ModuleLoader__:{load({factory}){factory(()=>React);}}},document:{addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)}};
  vm.runInNewContext(source.replace("return {inject:['slots','locale'],apply(ctx){","globalThis.Help=Help;return {inject:['slots','locale'],apply(ctx){"),context);
  let cleanup=()=>{};const render=()=>{cleanup();effects.length=0;cursor=0;const tree=context.Help({t:key=>key});cleanup=effects[0]()??(()=>{});return tree;};
  let tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);
  tree.props.onMouseEnter();tree=render();assert.equal(tree.children[1].props.role,'tooltip');
  tree.props.onMouseLeave();tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);
  tree.children[0].props.onFocus();tree=render();assert.equal(tree.children[0].props['aria-expanded'],true);
  tree.children[0].props.onClick();tree.props.onMouseLeave();tree.children[0].props.onBlur();tree=render();assert.equal(tree.children[0].props['aria-expanded'],true);
  listeners.get('keydown')({key:'Escape'});tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);
  tree.children[0].props.onClick();tree=render();listeners.get('pointerdown')({target:'inside'});tree=render();assert.equal(tree.children[0].props['aria-expanded'],true);
  listeners.get('pointerdown')({target:'outside'});tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);
  tree.children[0].props.onClick();tree=render();listeners.get('keydown')({key:'Tab'});tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);
  tree.children[0].props.onClick();tree=render();tree.children[0].props.onClick();tree=render();assert.equal(tree.children[0].props['aria-expanded'],false);cleanup();assert.equal(listeners.size,0);
});

test('client embeds exact tested time core and uses native slots/theme without internal imports',async()=>{
  const core=await fs.readFile(new URL('time.js',import.meta.url),'utf8');const template=await fs.readFile(new URL('client.template.js',import.meta.url),'utf8');
  const outbox=await fs.readFile(new URL('outbox.js',import.meta.url),'utf8');
  assert.equal(source,(await embedLocaleDictionaries(template,new URL('./',import.meta.url))).replace('/* TIME_CORE */',()=>core.replace(/^export /gm,'')).replace('/* OUTBOX_CORE */',()=>outbox.replace(/^export /gm,'')));
  assert.match(source,/name:'main',key:'activity-analytics'/);assert.match(source,/name:'sidebar.panellist',id:'activity-analytics'/);
  assert.match(source,/ctx\.effect\(\(\)=>controller\.start\(\)\)/);assert.doesNotMatch(source,/require\(['"]@deepseek/);
  assert.doesNotMatch(source,/document\.(?:querySelector|body)|clipboard|\.target\.value.*interact/);
  for(const name of ['today','yesterday','7','14','28','all','custom'])assert.ok(source.includes(name));
  assert.doesNotMatch(source,/aa-footer|aa-rules|Stored locally|Current profile only/);
  assert.match(source,/function Help\(/);assert.match(source,/role:'tooltip'/);assert.match(source,/'aria-expanded':open/);assert.match(source,/e\.key==='Escape'\|\|e\.key==='Tab'/);
  assert.match(source,/aa-range-meta/);assert.match(source,/data\.trackingSince/);
  const interaction=source.slice(source.indexOf('const interact='),source.indexOf('const change=',source.indexOf('const interact=')));assert.doesNotMatch(interaction,/\.key\b|\.data\b|\.target\b/);
  assert.match(source,/registerMainframeLocale\(ctx\.locale,NS,en,ru\)/);assert.match(source,/--dsw-alias-bg-base/);
  const pkg=JSON.parse(await fs.readFile(new URL('package.json',import.meta.url),'utf8'));assert.equal(pkg.dsh.client.immediately,true);
  for(const locale of ['en','ru']){const doc=JSON.parse(await fs.readFile(new URL(`locale/${locale}.json`,import.meta.url),'utf8'));assert.ok(doc.meta.title&&doc.meta.description);}
});
