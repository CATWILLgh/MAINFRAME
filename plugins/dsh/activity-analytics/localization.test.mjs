import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import { embedLocaleDictionaries } from '../build-locales.mjs';
const root=new URL('./',import.meta.url);
const source=await fs.readFile(new URL('client.js',root),'utf8');
const template=await fs.readFile(new URL('client.template.js',root),'utf8');
const dictionaries=Object.fromEntries(await Promise.all(['en','ru'].map(async language=>[language,JSON.parse(await fs.readFile(new URL(`locale/${language}.json`,root),'utf8'))])));

test('central dictionaries cover interface keys, metadata and generated output exactly',async()=>{
  assert.deepEqual(Object.keys(dictionaries.en.ui).sort(),Object.keys(dictionaries.ru.ui).sort());
  for(const dictionary of Object.values(dictionaries)){
    assert.ok(dictionary.meta.title&&dictionary.meta.description);
    for(const text of Object.values(dictionary.ui))assert.equal(typeof text,'string');
  }
  for(const [,key] of template.matchAll(/\bt\('([^']+)'\)/g))assert.ok(key in dictionaries.en.ui,`Missing ${key}`);
  for(const key of ['today','yesterday','7','14','28','all','custom','you','agents','youHelp','agentsHelp','recording','paused','invalid','error'])assert.ok(key in dictionaries.en.ui);
  assert.doesNotMatch(template,/[А-Яа-яЁё]/);
  assert.doesNotMatch(template,/const (en|ru)\s*=|\.pendingMs\/1000\)\.toFixed|DateTimeFormat\(locale\.getLocale/);
  let expected=await embedLocaleDictionaries(template,root);
  for(const [marker,file] of [['TIME_CORE','time.js'],['OUTBOX_CORE','outbox.js']])expected=expected.replace(`/* ${marker} */`,()=>(embeddedModules[file]).replace(/^export /gm,''));
  assert.equal(source,expected);
});
const embeddedModules=Object.fromEntries(await Promise.all(['time.js','outbox.js'].map(async file=>[file,await fs.readFile(new URL(file,root),'utf8')])));

function runtime(){
  let stateIndex=0,memoIndex=0;const formats=[],numbers=[],memos=[];
  const React={Fragment:'fragment',createElement:(type,props,...children)=>({type,props,children}),useSyncExternalStore:(_subscribe,getSnapshot)=>getSnapshot(),useState:initial=>{
    const index=stateIndex++;return [index===4?{start:1800000000000,end:1800000060000,trackingSince:1800000000000,userMs:60000,agentMs:60000,runningAgents:1}:typeof initial==='function'?initial():initial,()=>{}];
  },useRef:value=>({current:value}),useEffect(){},useMemo(factory,deps){const index=memoIndex++;if(!memos[index]||deps.some((value,i)=>value!==memos[index].deps[i]))memos[index]={deps,value:factory()};return memos[index].value;}};
  const context={window:{__ModuleLoader__:{load({factory}){factory(()=>React);}}},Intl:{DateTimeFormat:function(language,options){formats.push(language??'device');return new Intl.DateTimeFormat(language,options);},NumberFormat:function(language,options){numbers.push(language);return new Intl.NumberFormat(language,options);}}};
  vm.runInNewContext(source.replace("return {inject:['slots','locale'],apply(ctx){","globalThis.exposed={Page,en,ru,registerMainframeLocale};return {inject:['slots','locale'],apply(ctx){"),context);
  return {...context.exposed,formats,numbers,render(props){stateIndex=0;memoIndex=0;formats.length=0;numbers.length=0;return context.exposed.Page(props);}};
}
function nativeLocale(){
  let active='en',snapshot={locales:[{id:'en'},{id:'ru'},{id:'de'},{id:'zh'}]};const listeners=new Set(),registered=new Map();
  const notify=()=>{snapshot={...snapshot};for(const listener of listeners)listener();};
  return {registered,subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>snapshot,getLocale:()=>({active}),register(_namespace,id,dictionary){registered.set(id,dictionary);notify();return()=>registered.delete(id);},bind:()=>key=>registered.get(active)?.[key]??registered.get('ru')?.[key]??key,setLanguage(id){active=id;notify();},addLanguage(id){snapshot={locales:[...snapshot.locales,{id}]};notify();}};
}
function text(tree){if(typeof tree==='string'||typeof tree==='number')return String(tree);if(!tree)return '';return (tree.children??[]).flat(Infinity).map(text).join(' ');}
test('page reuses Intl formatters across frequent activity snapshots and replaces them on language or zone changes',()=>{
  const x=runtime(),locale=nativeLocale(),dispose=x.registerMainframeLocale(locale,'activityAnalytics',x.en,x.ru);
  const props={locale,controller:{subscribe(){},getSnapshot:()=>({active:true,pendingMs:1000,durable:true})},t:locale.bind('activityAnalytics')};
  x.render(props);assert.ok(x.formats.length>=3);assert.equal(x.numbers.length,1);
  for(let i=0;i<100;i++){x.render(props);assert.equal(x.formats.filter(value=>value!=='device').length,0);assert.equal(x.numbers.length,0);}
  locale.setLanguage('ru');assert.ok(text(x.render(props)).includes('1,0 с'));assert.ok(x.formats.includes('ru'));assert.deepEqual(x.numbers,['ru']);
  const zone=process.env.TZ;
  try { process.env.TZ='Pacific/Honolulu';x.render(props);assert.ok(x.formats.includes('ru')); }
  finally { if(zone===undefined)delete process.env.TZ;else process.env.TZ=zone;dispose(); }
});

test('native locale updates Russian/English text, units and Intl formatting without remount',()=>{
  const x=runtime(),locale=nativeLocale(),dispose=x.registerMainframeLocale(locale,'activityAnalytics',x.en,x.ru);
  const controller={subscribe(){return()=>{};},getSnapshot:()=>({active:true,pendingMs:1500,durable:true}),summary(){}};
  const props={locale,controller,t:locale.bind('activityAnalytics')};
  let previousLanguage;
  for(const [language,expected] of [['ru',dictionaries.ru.ui],['de',dictionaries.en.ui],['zh',dictionaries.en.ui],['en',dictionaries.en.ui],['ru',dictionaries.ru.ui]]){
    locale.setLanguage(language);const tree=x.render(props),rendered=text(tree);
    assert.equal(tree.props.lang,language==='ru'?'ru':'en');
    for(const key of ['panel','subtitle','today','you','agents','pending','second'])assert.ok(rendered.includes(expected[key]),`${language}: ${key}`);
    const effectiveLanguage=language==='ru'?'ru':'en';
    if(previousLanguage!==effectiveLanguage)assert.ok(x.formats.includes(effectiveLanguage));
    else assert.deepEqual(x.formats,['device']);
    previousLanguage=effectiveLanguage;
    assert.ok(x.formats.every(value=>value==='device'||value===(language==='ru'?'ru':'en')));
    assert.ok(rendered.includes(language==='ru'?'1,5 с':'1.5 s'));
  }
  locale.addLanguage('fr');locale.setLanguage('fr');assert.ok(text(x.render(props)).includes(dictionaries.en.ui.panel));
  dispose();assert.equal(locale.registered.size,0);
});
