// Synthetic CPU-only benchmark. Replaces queue/ownership in an in-memory copy;
// no store creation, disk state, network, clipboard, keys, or plugin activation.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
let source=await readFile(new URL('./core/index.js',import.meta.url),'utf8');
const start=source.indexOf('  #enqueue(run, capture) {'),end=source.indexOf('  #ownerState(pid)',start);
assert.ok(start>0&&end>start);
source=source.slice(0,start)+'  seed(rows) {this.#records=rows;this.#key=Buffer.alloc(1);}\n  #enqueue(run,capture) {return Promise.resolve().then(()=>run(capture?.()));}\n'+source.slice(end);
const {VaultStore}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
for(const size of [1000,4096]) {
 const rows=Array.from({length:size},(_,i)=>({id:String(i).padStart(5,'0'),created:'2026-01-01',updated:'2026-01-01',revision:1,metadata:{name:`Synthetic entry ${i}`,description:'Synthetic metadata '.repeat(10),kind:'token',tags:['fixture','benchmark']},secret:'SYNTHETIC-NEVER-RETURN'}));
 const store=new VaultStore({databasePath:'/synthetic-unused'},{filesystem:new Proxy({},{get(){throw new Error('Benchmark attempted filesystem access');}})});store.seed(rows);
 const result={records:size,iterations:200};
 for(const [label,fn] of [['fullCloneSort',()=>store.list()],['page100',()=>store.listPage({limit:100})],['lookup',()=>store.getMetadata('00000')]]) {
  for(let i=0;i<10;i++)await fn();const samples=[];
  for(let i=0;i<200;i++){const start=performance.now();await fn();samples.push(performance.now()-start);}
  samples.sort((a,b)=>a-b);result[label]={medianMs:+samples[100].toFixed(3),p95Ms:+samples[190].toFixed(3)};
 }
 const page=await store.listPage();assert.equal(page.records.length,100);assert.equal(page.records[0].id,'00000');assert.equal(page.records[99].id,'00099');assert.equal(JSON.stringify(page).includes('SYNTHETIC-NEVER-RETURN'),false);
 console.log(JSON.stringify(result));
}
