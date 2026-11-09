window.__ModuleLoader__.load({
  id:'@mainframe/activity-analytics',
  factory(require) {
    const React=require('react'), h=React.createElement;
    /* TIME_CORE */
    /* OUTBOX_CORE */
    const NS='activityAnalytics';
    /* LOCALE_DICTIONARIES */
    const css=`
.aa-page{font:inherit;color:var(--dsw-alias-label-primary);width:100%;height:100%;min-width:0;min-height:0;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;gap:32px;padding:0 clamp(24px,4vw,48px) 48px;overflow:auto;background:var(--dsw-alias-bg-base)}
.aa-page *{box-sizing:border-box}.aa-page>header,.aa-page>section{width:100%;max-width:960px;flex:none}
.aa-header{padding-top:28px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px}[data-platform=darwin] .aa-header{padding-top:calc(28px + var(--dsh-frame-top-clearance,0px))}
.aa-title{margin:0;font-size:20px;font-weight:500;line-height:28px}.aa-muted{color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}.aa-header p{margin:4px 0 0}
.aa-button{font:inherit;font-size:13px;line-height:20px;min-height:32px;padding:5px 12px;border:.5px solid var(--dsw-alias-border-l2);border-radius:16px;background:transparent;color:var(--dsw-alias-label-primary);cursor:pointer}.aa-button:hover:not(:disabled){background:var(--dsw-alias-bg-layer-2)}.aa-button:disabled{opacity:.45;cursor:default}.aa-button[aria-pressed=true]{background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-base);border-color:transparent}.aa-icon-button{width:32px;padding:6px;display:grid;place-items:center;flex:none}
.aa-page :is(button,input,summary):focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:3px}
.aa-presets{display:flex;gap:8px;flex-wrap:wrap}.aa-filter{display:flex;flex-direction:column;gap:16px}.aa-custom{display:flex;flex-wrap:wrap;align-items:end;gap:12px}.aa-custom label{display:flex;flex-direction:column;gap:6px;font-size:13px}.aa-custom input{font:inherit;font-size:14px;min-height:36px;padding:6px 10px;border:.5px solid var(--dsw-alias-border-l2);border-radius:10px;background:transparent;color:var(--dsw-alias-label-primary);max-width:100%}
.aa-range{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding-top:16px;border-top:.5px solid var(--dsw-alias-border-l1);margin:0}.aa-range time{font-variant-numeric:tabular-nums}
.aa-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.aa-metric{padding:24px 0;border-top:2px solid var(--dsw-alias-brand-primary);min-width:0}.aa-metric:last-child{border-color:var(--dsw-alias-label-secondary)}.aa-metric h2{font:inherit;font-size:14px;font-weight:500;line-height:22px;margin:0 0 20px}.aa-number{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;font-size:clamp(36px,5vw,56px);font-weight:500;letter-spacing:-1.5px;line-height:1.15;font-variant-numeric:tabular-nums;min-height:65px}.aa-number small{font-size:18px;font-weight:400;letter-spacing:0;margin-right:8px;color:var(--dsw-alias-label-secondary)}.aa-metric p{margin:12px 0 0}
.aa-status{display:flex;flex-wrap:wrap;gap:8px 24px;padding-top:16px;border-top:.5px solid var(--dsw-alias-border-l1)}.aa-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px;vertical-align:middle;background:var(--dsw-alias-state-idle-primary)}.aa-dot[data-active=true]{background:var(--dsw-alias-state-success-primary)}.aa-error{font-size:13px;color:var(--dsw-alias-state-error-primary);margin:0;line-height:20px}.aa-header>div{position:relative}.aa-subtitle{display:flex;align-items:center;gap:4px;margin-top:4px}.aa-help{display:inline-flex;flex:none}.aa-help-button{border:0;background:transparent;color:var(--dsw-alias-label-secondary);width:20px;height:20px;padding:0;display:grid;place-items:center;cursor:pointer;border-radius:4px}.aa-help-button:hover{background:var(--dsw-alias-bg-layer-2)}.aa-help-panel{position:absolute;top:calc(100% + 8px);left:0;z-index:20;width:min(420px,calc(100vw - 64px));max-height:70vh;overflow:auto;padding:16px;border:.5px solid var(--dsw-alias-border-l2);border-radius:12px;background:var(--dsw-alias-bg-base);box-shadow:0 6px 24px #0003;color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}.aa-help-panel strong{color:var(--dsw-alias-label-primary);font-weight:500}.aa-help-panel p{margin:10px 0 0}.aa-range-meta{display:flex;flex-direction:column;gap:4px}.aa-empty{margin:0}
@media(max-width:600px){.aa-metrics{grid-template-columns:1fr;gap:8px}.aa-number{font-size:44px}.aa-metric{padding:20px 0}.aa-page{gap:24px}}
`;
    function Icon({size=20}) {return h('svg',{width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('path',{d:'M4 19V12M10 19V7M16 11V3',strokeLinecap:'round'}),h('circle',{cx:17,cy:17,r:4}),h('path',{d:'M17 14.5V17l1.5 1',strokeLinecap:'round'}));}
    function Refresh(){return h('svg',{width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('path',{d:'M20 11a8 8 0 1 0-2 6M20 4v7h-7',strokeLinecap:'round',strokeLinejoin:'round'}));}
    function Help({t}) {
      const [hover,setHover]=React.useState(false),[focused,setFocused]=React.useState(false),[pinned,setPinned]=React.useState(false),[dismissed,setDismissed]=React.useState(false),root=React.useRef(null),id=React.useId();
      const open=!dismissed&&(hover||focused||pinned);
      React.useEffect(()=>{if(!open)return;const close=e=>{if(!root.current?.contains(e.target)){setPinned(false);setFocused(false);setHover(false);setDismissed(true);}};const key=e=>{if(e.key==='Escape'||e.key==='Tab'){setPinned(false);setDismissed(true);}};document.addEventListener('pointerdown',close,true);document.addEventListener('keydown',key,true);return()=>{document.removeEventListener('pointerdown',close,true);document.removeEventListener('keydown',key,true);};},[open]);
      return h('div',{className:'aa-help',ref:root,onMouseEnter:()=>{setHover(true);setDismissed(false);},onMouseLeave:()=>setHover(false)},h('button',{type:'button',className:'aa-help-button','aria-label':t('rules'),'aria-expanded':open,'aria-describedby':open?id:undefined,onFocus:()=>{setFocused(true);setDismissed(false);},onBlur:()=>setFocused(false),onClick:()=>{if(pinned){setPinned(false);setDismissed(true);}else{setPinned(true);setDismissed(false);}}},h('svg',{width:11,height:11,viewBox:'0 0 16 16',fill:'none',stroke:'currentColor',strokeWidth:1.3,'aria-hidden':true},h('circle',{cx:8,cy:8,r:6.3}),h('path',{d:'M8 7v4M8 4.4v.2',strokeLinecap:'round'}))),open&&h('div',{id,role:'tooltip',className:'aa-help-panel'},h('strong',null,t('rules')),['ruleUser','ruleAgent','ruleDates','rulePrivacy','ruleBrowser'].map(key=>h('p',{key},t(key)))));
    }
    async function api(body,keepalive=false) {
      const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),8000);
      try {const response=await fetch('/api/activity-analytics/ui',{method:'POST',headers:{'content-type':'application/json','x-activity-analytics-ui':'1'},body:JSON.stringify(body),signal:abort.signal,keepalive});if(!response.ok)throw new Error('request');const value=await response.json();if(value.ok!==true)throw new Error('request');return value;} finally {clearTimeout(timer);}
    }
    function createController() {
      let snapshot={active:false,syncError:false,pendingMs:0,durable:false,storageError:false,recoveryError:false,lastSavedAt:null},disposed=false,flight=null,lastPointer=-Infinity,initialized=false;
      const id=globalThis.crypto.randomUUID();
      let outbox=createOutbox({id});
      const listeners=new Set(),clock=createActivityClock();
      const publish=patch=>{snapshot={...snapshot,...patch};if(!disposed)listeners.forEach(fn=>fn());};
      const focused=()=>document.visibilityState==='visible'&&document.hasFocus();
      const queueState=()=>{const s=outbox.getState();publish({pendingMs:s.pendingMs,durable:s.durable,storageError:!!s.error,recoveryError:!!s.recoveryError});};
      async function initialize(){
        if(initialized)return;
        const {queueScope}=await api({op:'bootstrap'});
        if(typeof queueScope!=='string'||! /^[a-f0-9]{64}$/.test(queueScope))throw new Error('scope');
        let storage=null;try{storage=window.localStorage;}catch{}
        // A new durable instance must never reuse an older snapshot identity.
        const restored=createOutbox({storage,scope:queueScope,id:globalThis.crypto.randomUUID()});
        restored.add(outbox.getPending());outbox=restored;initialized=true;queueState();
      }
      function sample(interaction=false,forceInactive=false){
        if(disposed)return;
        const wall=Date.now(),mono=performance.now(),active=!forceInactive&&focused();
        const intervals=clock.step({wall,mono,focused:active,interaction});
        if(intervals.length){outbox.add(intervals);queueState();}
        if(interaction&&active)lastPointer=mono;
        const recording=clock.isActive();
        if(snapshot.active!==recording)publish({active:recording});
      }
      async function flush(keepalive=false){
        if(flight)return flight;
        flight=(async()=>{
          try{
            await initialize();
            // Drain a bounded snapshot of backlog, never an endlessly growing live tail.
            const through=outbox.getPending().at(-1)?.end;
            while(through!==undefined){
              const batch=outbox.getBatch().filter(v=>v.start<through).map(v=>({start:v.start,end:Math.min(v.end,through)}));
              if(!batch.length)break;
              const result=await api({op:'activity',intervals:batch},keepalive);
              // The Host may clip a client clock slightly ahead of its own time.
              if(!Number.isSafeInteger(result.persistedThrough))throw new Error('ack');
              const acknowledged=batch.filter(v=>v.start<result.persistedThrough).map(v=>({start:v.start,end:Math.min(v.end,result.persistedThrough)}));
              outbox.ack(acknowledged);queueState();publish({syncError:false,lastSavedAt:Date.now()});
              if(batch.some(v=>v.end>result.persistedThrough)){publish({syncError:true});return false;}
            }
            publish({syncError:false});return true;
          }catch{publish({syncError:true});queueState();return false;}
        })().finally(()=>{flight=null;});
        return flight;
      }
      return {getSnapshot:()=>snapshot,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},sample,flush,
        async summary(range){sample();await flush();return api({op:'summary',...range});},
        start(){lastPointer=performance.now();sample(true);void flush();let ticks=0;
          const interact=e=>{if(e.isTrusted===false)return;if(e.type==='scroll'){sample(false);return;}if((e.type==='pointermove'||e.type==='touchmove')&&performance.now()-lastPointer<1000)return;sample(true);};
          const change=()=>{sample(false);void flush();};
          const hide=()=>{sample(false,true);void flush(true);};
          const activityEvents=['keydown','pointerdown','pointermove','wheel','scroll','touchstart','touchmove','beforeinput','input','compositionstart','compositionupdate'];
          activityEvents.forEach(name=>window.addEventListener(name,interact,{capture:true,passive:true}));
          window.addEventListener('focus',change);window.addEventListener('blur',change);document.addEventListener('visibilitychange',change);window.addEventListener('pagehide',hide);
          const timer=setInterval(()=>{sample();if(++ticks%2===0)void flush();},5000);
          return ()=>{sample(false,true);void flush(true);disposed=true;clearInterval(timer);activityEvents.forEach(name=>window.removeEventListener(name,interact,true));window.removeEventListener('focus',change);window.removeEventListener('blur',change);document.removeEventListener('visibilitychange',change);window.removeEventListener('pagehide',hide);listeners.clear();};
        }
      };
    }
    function dateInput(now){const d=new Date(now);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
    function Page({controller,t,locale}) {
      React.useSyncExternalStore(locale.subscribe.bind(locale),locale.getSnapshot.bind(locale),locale.getSnapshot.bind(locale));
      const activity=React.useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getSnapshot);
      const [preset,setPreset]=React.useState('today'),[from,setFrom]=React.useState(()=>dateInput(Date.now())),[to,setTo]=React.useState(()=>dateInput(Date.now())),[custom,setCustom]=React.useState(null),[data,setData]=React.useState(null),[error,setError]=React.useState(''),[busy,setBusy]=React.useState(true),[revision,setRevision]=React.useState(0);
      const tracking=React.useRef(null),view=React.useRef(0);
      React.useEffect(()=>{let live=true,loading=false;const token=++view.current;
        async function load(){if(loading)return;loading=true;setBusy(true);try{
          if(tracking.current===null){const boot=await controller.summary({start:0,end:Date.now()});tracking.current=boot.trackingSince;}
          const range=resolveRange(preset,Date.now(),tracking.current,custom?.from,custom?.to);
          const result=await controller.summary(range);
          if(live&&token===view.current){setData(result);setError('');}
        }catch{if(live&&token===view.current)setError('error');}finally{loading=false;if(live&&token===view.current)setBusy(false);}}
        setData(null);void load();const timer=setInterval(()=>void load(),15000);return()=>{live=false;clearInterval(timer);};
      },[preset,custom,revision]);
      const language=locale.getLocale().active.toLowerCase()==='ru'?'ru':'en';
      const timeZone=Intl.DateTimeFormat().resolvedOptions().timeZone;
      const formats=React.useMemo(()=>({
        date:new Intl.DateTimeFormat(language,{timeZone,day:'numeric',month:'short',year:'numeric'}),
        since:new Intl.DateTimeFormat(language,{timeZone,day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}),
        saved:new Intl.DateTimeFormat(language,{timeZone,hour:'2-digit',minute:'2-digit',second:'2-digit'}),
        pending:new Intl.NumberFormat(language,{minimumFractionDigits:1,maximumFractionDigits:1})
      }),[language,timeZone]);
      const fmt=(ts,kind)=>formats[kind].format(ts);
      function duration(ms){const total=Math.floor(ms/60000),hours=Math.floor(total/60),minutes=total%60;return h(React.Fragment,null,String(hours),h('small',null,t('hour')),String(minutes).padStart(2,'0'),h('small',null,t('minute')));}
      const metric=(key,value,help)=>h('article',{className:'aa-metric'},h('h2',null,t(key)),h('div',{className:'aa-number','aria-label':value===undefined?t('loading'):`${Math.floor(value/3600000)} ${t('hour')} ${Math.floor(value/60000)%60} ${t('minute')}`},value===undefined?'—':duration(value)),h('p',{className:'aa-muted'},t(help)),value>0&&value<60000&&h('p',{className:'aa-muted'},t('seconds')));
      return h('div',{className:'aa-page',lang:language},h('style',null,css),h('header',{className:'aa-header'},h('div',null,h('h1',{className:'aa-title'},t('panel')),h('div',{className:'aa-subtitle aa-muted'},h('span',null,t('subtitle')),h(Help,{t}))),h('button',{type:'button',className:'aa-button aa-icon-button',title:t('refresh'),'aria-label':t('refresh'),disabled:busy,onClick:()=>setRevision(v=>v+1)},h(Refresh))),
        h('section',{className:'aa-filter','aria-label':t('selected')},h('div',{className:'aa-presets'},['today','yesterday','7','14','28','all','custom'].map(key=>h('button',{key,type:'button',className:'aa-button','aria-pressed':preset===key,onClick:()=>{setError('');if(key==='custom'&&!custom)setCustom({from,to});setPreset(key);}},t(key)))),preset==='custom'&&h('form',{className:'aa-custom',onSubmit:e=>{e.preventDefault();try{resolveRange('custom',Date.now(),tracking.current??Date.now(),from,to);setCustom({from,to});setError('');}catch{setError('invalid');}}},h('label',null,t('from'),h('input',{type:'date',required:true,value:from,max:dateInput(Date.now()),onChange:e=>setFrom(e.target.value)})),h('label',null,t('to'),h('input',{type:'date',required:true,value:to,max:dateInput(Date.now()),onChange:e=>setTo(e.target.value)})),h('button',{className:'aa-button',type:'submit'},t('apply'))),h('div',{className:'aa-range aa-muted'},h('span',null,data?`${fmt(data.start,'date')} — ${fmt(Math.max(data.start,data.end-1),'date')}`:t('loading')),h('div',{className:'aa-range-meta'},h('span',null,`${t('timezone')}: ${timeZone}`),data&&h('span',null,`${t('since')} ${fmt(data.trackingSince,'since')}`)))),
        (error||activity.syncError||activity.recoveryError||(activity.pendingMs>0&&!activity.durable))&&h('section',{'aria-live':'polite'},error&&h('p',{className:'aa-error',role:'alert'},t(error)),activity.syncError&&h('p',{className:'aa-error'},t('activityError')),activity.pendingMs>0&&!activity.durable&&h('p',{className:'aa-error'},t('volatile')),activity.recoveryError&&h('p',{className:'aa-error'},t('recoveryError'))),
        h('section',{className:'aa-metrics','aria-busy':busy},metric('you',data?.userMs,'youHelp'),metric('agents',data?.agentMs,'agentsHelp')),
        h('section',{className:'aa-status aa-muted'},h('span',null,h('i',{className:'aa-dot','data-active':activity.active}),t(activity.active?'recording':'paused')),h('span',null,`${t('running')}: ${data?.runningAgents??'—'}`),h('span',{'aria-live':'polite'},activity.pendingMs>0?`${t('pending')}: ${formats.pending.format(activity.pendingMs/1000)} ${t('second')}`:activity.lastSavedAt?`${t('saved')} · ${t('savedAt')} ${fmt(activity.lastSavedAt,'saved')}`:t('loading')),data&&data.userMs===0&&data.agentMs===0&&h('p',{className:'aa-empty'},t('noData'))));
    }
    return {inject:['slots','locale'],apply(ctx){
      ctx.effect(()=>registerMainframeLocale(ctx.locale,NS,en,ru));const t=ctx.locale.bind(NS),controller=createController();
      ctx.effect(()=>controller.start());
      ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:'activity-analytics',order:20,label:()=>t('panel'),locale:NS},Icon));
      ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:'activity-analytics',locale:NS,inject:()=>({controller,t,locale:ctx.locale})},Page));
    }};
  }
});
