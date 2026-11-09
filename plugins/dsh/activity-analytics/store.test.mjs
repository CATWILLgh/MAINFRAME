import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { ActivityStore, InputError, MAX_BATCH } from './store.js';
import { DatabaseSync } from 'node:sqlite';

async function fixture(t, initial = 1_000_000) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'activity-analytics-store-'));
  t.after(async () => {
    assert.ok(directory.startsWith(path.join(os.tmpdir(), 'activity-analytics-store-')));
    await fs.rm(directory, { recursive: true, force: true });
  });
  let time = initial;
  const now = () => time;
  const store = await ActivityStore.open(directory, { now });
  return { store, directory, now, at: n => { time = n; } };
}

test('global user union deduplicates retries and overlapping windows; query clips exactly', async t => {
  const { store, at } = await fixture(t);
  at(1_100_000);
  await store.activity([{ start: 999_000, end: 1_010_000 }, { start: 1_020_000, end: 1_040_000 }], 'window-one');
  await store.activity([{ start: 1_005_000, end: 1_025_000 }], 'window-two');
  await store.activity([{ start: 1_005_000, end: 1_025_000 }], 'window-two');
  assert.equal((await store.summary(0, 2_000_000)).userMs, 40_000);
  assert.equal((await store.summary(1_010_123, 1_030_789)).userMs, 20_666);
  assert.equal((await store.summary(0, 999_999)).userMs, 0);
  assert.equal((await store.summary(1_025_000, 1_025_000)).userMs, 0);
  assert.deepEqual(store.db.prepare('SELECT start,end FROM user_intervals').all().map(r=>[r.start,r.end]), [[1_000_000, 1_040_000]]);
});

test('parallel parent and child agents sum, duplicate starts do not, idle/dispose stop', async t => {
  const { store, at } = await fixture(t);
  const parent = {}, child = {};
  await store.setRunning(parent, true);
  at(1_005_000); await store.setRunning(child, true);
  at(1_010_000); await store.setRunning(parent, true);
  at(1_015_000); await store.setRunning(child, false);
  at(1_020_000); await store.setRunning(parent, false);
  assert.equal((await store.summary(0, 2_000_000)).agentMs, 30_000);
  assert.equal((await store.summary(1_007_123, 1_012_456)).agentMs, 10_666);
  at(1_100_000);
  assert.equal((await store.summary(0, 2_000_000)).agentMs, 30_000);
});

test('summary includes current running time, capped gaps discard sleep and clock rollback', async t => {
  const { store, at } = await fixture(t);
  const agent = {};
  await store.setRunning(agent, true);
  at(1_005_000);
  assert.equal((await store.summary(0, 2_000_000)).agentMs, 5_000);
  at(2_000_000); await store.checkpoint(); // A suspend is not an hour of work.
  assert.equal((await store.summary(0, 3_000_000)).agentMs, 5_000);
  at(2_010_000); await store.checkpoint();
  at(1_999_000); await store.checkpoint(); // Do not rewind and recount.
  at(2_015_000); await store.setRunning(agent, false);
  assert.equal((await store.summary(0, 3_000_000)).agentMs, 20_000);
});

test('restart preserves trackingSince and completed checkpoints but never revives running agents', async t => {
  const { store, directory, at, now } = await fixture(t);
  await store.setRunning({ id: 'never-persist-this-id' }, true);
  at(1_015_000); await store.checkpoint();
  await store.activity([{ start: 1_000_000, end: 1_010_000 }], 'do-not-persist-client-id');
  at(10_000_000); // Simulate hard crash: do not close first instance.
  const reopened = await ActivityStore.open(directory, { now });
  const summary = await reopened.summary(0, 11_000_000);
  assert.equal(summary.trackingSince, 1_000_000);
  assert.equal(summary.userMs, 10_000);
  assert.equal(summary.agentMs, 15_000);
  assert.equal(summary.runningAgents, 0);
  for (const name of await fs.readdir(directory)) {
    const disk = await fs.readFile(path.join(directory,name));
    assert.ok(!disk.includes('persist-this-id'));
    assert.ok(!disk.includes('persist-client-id'));
  }
  assert.equal((await fs.stat(directory)).mode & 0o777, 0o700);
  assert.equal((await fs.stat(path.join(directory, 'intervals.sqlite'))).mode & 0o777, 0o600);
  await reopened.close();
});

test('serial writes preserve concurrent activity and transitions, persisted file reloads', async t => {
  const { store, directory, at, now } = await fixture(t);
  at(1_010_000);
  await Promise.all(Array.from({ length: 40 }, (_, n) => store.activity([{ start: 1_000_000 + n * 100, end: 1_000_500 + n * 100 }])));
  const reopened = await ActivityStore.open(directory, { now });
  assert.equal((await reopened.summary(0, 2_000_000)).userMs, 4_400);
  assert.ok((await fs.readdir(directory)).includes('intervals.sqlite'));
  assert.ok(!(await fs.readdir(directory)).includes('intervals.json'));
  await reopened.close();
});

test('bounded all-or-nothing input and future clipping; retry old intervals is valid', async t => {
  const { store, at } = await fixture(t);
  at(2_000_000);
  for (const intervals of [null, Array(MAX_BATCH + 1).fill({ start: 1_000_000, end: 1_000_001 }), [{ start: NaN, end: 1_000_001 }], [{ start: 1_000_000, end: 1_030_001 }], [{ start: 1_000_000, end: 1_000_001, text: 'not allowed' }], [{ start: 2_030_000, end: 2_030_001 }]]) {
    await assert.rejects(store.activity(intervals), InputError);
  }
  await assert.rejects(store.activity([], 'invalid client id'), InputError);
  await assert.rejects(store.summary(5, 1), InputError);
  await store.activity([{ start: 1_000_000, end: 1_001_000 }, { start: 1_999_000, end: 2_001_000 }]);
  assert.equal((await store.summary(0, 3_000_000)).userMs, 2_000);
});

test('failed persistence retains dirty numeric intervals for retry without duplicate counting', async t => {
  const { store, at } = await fixture(t);
  at(1_010_000);
  const persist = store.persist.bind(store);
  store.persist = async () => { throw new Error('synthetic disk unavailable'); };
  await assert.rejects(store.activity([{ start: 1_000_000, end: 1_010_000 }]));
  assert.deepEqual(store.pendingUsers, [[1_000_000, 1_010_000]]);
  assert.equal(store.dirty, true);
  store.persist = persist;
  await store.activity([{ start: 1_000_000, end: 1_005_000 }]);
  assert.equal((await store.summary(0, 2_000_000)).userMs, 10_000);
  assert.equal(store.dirty, false);
});

test('failed stop/start writes preserve exact live state and retry without phantom running time', async t => {
  const { store, directory, now, at } = await fixture(t);
  const parent = {}, child = {};
  await store.setRunning(parent, true);
  at(1_005_000); await store.checkpoint();
  const persist = store.persist.bind(store);
  store.persist = async () => { throw new Error('synthetic disk unavailable'); };
  at(1_010_000); await assert.rejects(store.setRunning(parent, false));
  assert.equal(store.active.size, 0);
  at(1_015_000); await assert.rejects(store.setRunning(child, true));
  assert.equal(store.active.has(child), true);
  at(1_020_000); await assert.rejects(store.setRunning(child, false));
  assert.equal(store.active.size, 0);
  store.persist = persist;
  at(1_025_000);
  assert.equal((await store.summary(0, 2_000_000)).agentMs, 15_000);
  const reopened = await ActivityStore.open(directory, { now });
  assert.equal((await reopened.summary(0, 2_000_000)).agentMs, 15_000);
});

test('close rejects new admission immediately, drains accepted operations and is single-shot', async t => {
  const { store, at } = await fixture(t);
  let release;
  store.serial = new Promise(resolve => { release = resolve; });
  at(1_005_000);
  const accepted = store.activity([{ start: 1_000_000, end: 1_005_000 }]);
  const closing = store.close();
  const late = assert.rejects(store.checkpoint(), /clos/i);
  assert.equal(store.close(), closing);
  release();
  await Promise.all([accepted, closing, late]);
  assert.equal(store.closed, true);
  assert.throws(() => store.db.prepare('SELECT 1'), /closed|not open/i);
});

test('close retries transient final flush once without duplicate intervals', async t => {
  const { store, at, directory, now } = await fixture(t);
  await store.setRunning({}, true);
  at(1_010_000);
  const persist = store.persist.bind(store);
  let attempts = 0;
  store.persist = async () => {
    if (++attempts === 1) throw new Error('synthetic transient failure');
    return persist();
  };
  await store.close();
  assert.equal(attempts, 2);
  assert.equal(store.active.size, 0);
  const reopened = await ActivityStore.open(directory, { now });
  try { assert.equal((await reopened.summary(0, 2_000_000)).agentMs, 10_000); }
  finally { await reopened.close(); }
});

test('close releases database and live agents even while a real SQLite writer holds a lock', async t => {
  const { store, at } = await fixture(t);
  await store.setRunning({}, true);
  at(1_010_000);
  store.db.exec('PRAGMA busy_timeout=0');
  const writer = new DatabaseSync(store.file);
  writer.exec('BEGIN IMMEDIATE');
  try {
    const closing = store.close();
    await assert.rejects(closing, /locked/);
    assert.equal(store.close(), closing);
    assert.equal(store.closed, true);
    assert.equal(store.active.size, 0);
    assert.throws(() => store.db.prepare('SELECT 1'), /closed|not open/i);
    await assert.rejects(store.checkpoint(), /clos/i);
  } finally { writer.exec('ROLLBACK'); writer.close(); }
});

test('partial unpublished database is ignored; corrupt canonical database fails closed', async t => {
  const { store, directory, now } = await fixture(t);
  await store.close();
  await fs.writeFile(path.join(directory, '.intervals-interrupted.sqlite.tmp'), '{"partial":');
  const reopened = await ActivityStore.open(directory, { now }); await reopened.close();
  await fs.writeFile(path.join(directory, 'intervals.sqlite'), '{"broken":');
  await assert.rejects(ActivityStore.open(directory, { now }));
  assert.equal(await fs.readFile(path.join(directory, 'intervals.sqlite'), 'utf8'), '{"broken":');
});

async function legacyFixture(t, state = {version:1,trackingSince:1_000_000,updatedAt:1_100_000,userIntervals:[[1_000_000,1_020_000],[1_030_000,1_040_000]],agentIntervals:[[1_000_000,1_010_000,2],[1_010_000,1_030_000,1]]}) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(),'activity-analytics-migration-'));
  t.after(async()=>{assert.ok(directory.startsWith(path.join(os.tmpdir(),'activity-analytics-migration-')));await fs.rm(directory,{recursive:true,force:true});});
  const file = path.join(directory,'intervals.json');
  const original=JSON.stringify(state);await fs.writeFile(file,original,{mode:0o640});
  return {directory,file,original,now:()=>1_100_000};
}

test('migration transaction preserves totals, trackingSince and byte-for-byte untouched legacy backup; SQLite is authoritative', async t => {
  const f=await legacyFixture(t);
  const before=await fs.stat(f.file);
  let store=await ActivityStore.open(f.directory,{now:f.now});
  let summary=await store.summary(0,2_000_000);
  assert.equal(summary.trackingSince,1_000_000);assert.equal(summary.userMs,30_000);assert.equal(summary.agentMs,40_000);
  assert.equal(summary.runningAgents,0);
  assert.equal(await fs.readFile(f.file,'utf8'),f.original);
  const after=await fs.stat(f.file);assert.equal(after.mtimeMs,before.mtimeMs);assert.equal(after.mode,before.mode);
  await store.activity([{start:1_040_000,end:1_050_000}]);await store.close();
  await fs.writeFile(f.file,'corrupt old backup');
  store=await ActivityStore.open(f.directory,{now:f.now});
  summary=await store.summary(0,2_000_000);assert.equal(summary.userMs,40_000);assert.equal(summary.agentMs,40_000);
  await store.close();
});

test('failed migration commit rolls back, publishes no canonical DB and can be retried exactly once', async t => {
  const f=await legacyFixture(t);const exec=DatabaseSync.prototype.exec;let injected=false;
  DatabaseSync.prototype.exec=function(sql){if(sql==='COMMIT'&&!injected){injected=true;throw new Error('synthetic migration commit failure');}return exec.call(this,sql);};
  try {await assert.rejects(ActivityStore.open(f.directory,{now:f.now}),/synthetic migration/);} finally {DatabaseSync.prototype.exec=exec;}
  assert.equal(injected,true);assert.deepEqual(await fs.readdir(f.directory),['intervals.json']);
  assert.equal(await fs.readFile(f.file,'utf8'),f.original);
  const store=await ActivityStore.open(f.directory,{now:f.now});
  assert.equal((await store.summary(0,2_000_000)).agentMs,40_000);await store.close();
  const again=await ActivityStore.open(f.directory,{now:f.now});assert.equal((await again.summary(0,2_000_000)).agentMs,40_000);await again.close();
});

test('invalid or malformed legacy history fails closed without creating a database', async t => {
  for(const state of [{version:1,trackingSince:1,updatedAt:50,userIntervals:[[2,20],[10,30]],agentIntervals:[]},{version:1,trackingSince:1,updatedAt:50,userIntervals:[],agentIntervals:[[1,20,0]]},null]){
    const f=await legacyFixture(t,state);
    await assert.rejects(ActivityStore.open(f.directory,{now:f.now}));
    assert.deepEqual(await fs.readdir(f.directory),['intervals.json']);assert.equal(await fs.readFile(f.file,'utf8'),f.original);
  }
  const f=await legacyFixture(t);await fs.writeFile(f.file,'{"broken":');
  await assert.rejects(ActivityStore.open(f.directory,{now:f.now}));assert.deepEqual(await fs.readdir(f.directory),['intervals.json']);
});

test('real SQL failure rolls back entire incremental batch, retaining live stop and pending intervals for retry', async t => {
  const {store,at}=await fixture(t);const agent={};await store.setRunning(agent,true);
  store.db.exec("CREATE TRIGGER synthetic_failure BEFORE INSERT ON agent_intervals BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END");
  at(1_010_000);await assert.rejects(store.activity([{start:1_000_000,end:1_010_000}]),/synthetic disk/);
  assert.equal(store.db.prepare('SELECT COUNT(*) AS n FROM user_intervals').get().n,0);
  assert.equal(store.db.prepare('SELECT updatedAt FROM metadata').get().updatedAt,1_000_000);
  at(1_015_000);await assert.rejects(store.setRunning(agent,false));assert.equal(store.active.size,0);
  store.db.exec('DROP TRIGGER synthetic_failure');at(1_020_000);
  const summary=await store.summary(0,2_000_000);assert.equal(summary.agentMs,15_000);assert.equal(summary.userMs,10_000);
  assert.deepEqual(store.pendingAgents,[]);assert.deepEqual(store.pendingUsers,[]);
});

test('large indexed history supports narrow overlap queries and incremental writes without heap history or full rewrite', async t => {
  const rows=Array.from({length:20_000},(_,n)=>[1_000_000+n*100,1_000_050+n*100]);
  const f=await legacyFixture(t,{version:1,trackingSince:1_000_000,updatedAt:3_100_000,userIntervals:rows,agentIntervals:rows.map(([a,b])=>[a,b,2])});
  const store=await ActivityStore.open(f.directory,{now:()=>3_100_000});
  assert.equal(store.state.userIntervals,undefined);assert.equal(store.state.agentIntervals,undefined);
  const summary=await store.summary(2_999_025,2_999_125);assert.equal(summary.userMs,50);assert.equal(summary.agentMs,100);
  for(const table of ['user_intervals','agent_intervals']){
    const plans=store.db.prepare(`EXPLAIN QUERY PLAN SELECT end FROM ${table} WHERE start>=? AND start<? AND end>?`).all(2_999_000,2_999_200,2_999_025);
    assert.ok(plans.some(p=>p.detail.includes('SEARCH')&&p.detail.includes('INTEGER PRIMARY KEY')),JSON.stringify(plans));
  }
  const changes=store.db.prepare('SELECT total_changes() AS n').get().n;
  await store.activity([{start:3_050_000,end:3_060_000}]);
  assert.ok(store.db.prepare('SELECT total_changes() AS n').get().n-changes<=3);
  assert.equal(store.db.prepare('SELECT COUNT(*) AS n FROM user_intervals').get().n,20_001);
  assert.deepEqual(store.pendingUsers,[]);assert.deepEqual(store.pendingAgents,[]);await store.close();
});

test('schema version, extra schema objects, logical overlap and failed integrity check all fail closed', async t => {
  for(const damage of [db=>db.exec('PRAGMA user_version=2'),db=>db.exec('CREATE TABLE unexpected(secret TEXT)'),db=>db.exec('INSERT INTO user_intervals VALUES (1000001,1000003); INSERT INTO user_intervals VALUES (1000002,1000004); UPDATE metadata SET updatedAt=1000010'),db=>db.exec('PRAGMA ignore_check_constraints=ON; INSERT INTO user_intervals VALUES (1000002,1000001)')]){
    const {store,directory,now}=await fixture(t);await store.close();
    const db=new DatabaseSync(path.join(directory,'intervals.sqlite'));damage(db);db.close();
    await assert.rejects(ActivityStore.open(directory,{now}));
    assert.ok((await fs.stat(path.join(directory,'intervals.sqlite'))).size>0);
  }
});

test('out-of-order random overlapping windows remain an exact union including adjacent bridges and indexed predecessor clips', async t => {
  const {store,at}=await fixture(t);at(1_010_000);const covered=new Set();let seed=12345;
  for(let n=0;n<150;n++){
    seed=(seed*1664525+1013904223)>>>0;const start=seed%1000;
    seed=(seed*1664525+1013904223)>>>0;const end=start+1+seed%40;
    await store.activity([{start:1_000_000+start,end:1_000_000+end}]);for(let x=start;x<end;x++)covered.add(x);
  }
  assert.equal((await store.summary(0,2_000_000)).userMs,covered.size);
  for(let a=0;a<1100;a+=37){let expected=0;for(let x=a;x<a+71;x++)if(covered.has(x))expected++;assert.equal((await store.summary(1_000_000+a,1_000_000+a+71)).userMs,expected);}
  await store.activity([{start:1_002_000,end:1_002_010},{start:1_002_020,end:1_002_030},{start:1_002_010,end:1_002_020}]);
  assert.equal(store.db.prepare('SELECT COUNT(*) AS n FROM user_intervals WHERE start>=1002000').get().n,1);
  assert.equal((await store.summary(1_002_005,1_002_025)).userMs,20);
});

test('SQLite busy write preserves numeric deltas and exact stopped state until transaction retry', async t => {
  const {store,at}=await fixture(t);const agent={};await store.setRunning(agent,true);
  store.db.exec('PRAGMA busy_timeout=0');const blocker=new DatabaseSync(store.file);blocker.exec('BEGIN IMMEDIATE');
  at(1_010_000);try{await assert.rejects(store.activity([{start:1_000_000,end:1_010_000}]),/locked/);at(1_015_000);await assert.rejects(store.setRunning(agent,false),/locked/);assert.equal(store.active.size,0);}finally{blocker.exec('ROLLBACK');blocker.close();}
  at(1_020_000);const summary=await store.summary(0,2_000_000);assert.equal(summary.userMs,10_000);assert.equal(summary.agentMs,15_000);assert.equal(store.dirty,false);
});

test('empty existing canonical SQLite cannot silently reset or reimport valid JSON', async t => {
  const f=await legacyFixture(t);await fs.writeFile(path.join(f.directory,'intervals.sqlite'),'');
  await assert.rejects(ActivityStore.open(f.directory,{now:f.now}),/schema/);
  assert.equal((await fs.stat(path.join(f.directory,'intervals.sqlite'))).size,0);
  assert.equal(await fs.readFile(f.file,'utf8'),f.original);
});

test('clean close checkpoints, stops, and rejects further work', async t => {
  const { store, at } = await fixture(t);
  await store.setRunning({}, true);
  at(1_010_000); await store.checkpoint();
  assert.equal(store.db.prepare('SELECT end FROM agent_intervals').get().end, 1_010_000);
  await store.close();
  assert.equal(store.active.size, 0);
  await assert.rejects(store.checkpoint(), /closed/);
});
