import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';

test('native pnpm package resolves profile without environment or source checkout', async t => {
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'analytics-native-profile-'));
 const previous=process.env.DSH_PROFILE_DIR;
 delete process.env.DSH_PROFILE_DIR;
 t.after(async()=>{if(previous===undefined)delete process.env.DSH_PROFILE_DIR;else process.env.DSH_PROFILE_DIR=previous;assert.ok(root.startsWith(path.join(os.tmpdir(),'analytics-native-profile-')));await fs.rm(root,{recursive:true});});
 const installed=path.join(root,'node_modules','.pnpm','synthetic-package','node_modules','@mainframe','activity-analytics');
 await fs.mkdir(installed,{recursive:true});
 const source=fileURLToPath(new URL('.',import.meta.url));
 for(const name of await fs.readdir(source))if(name.endsWith('.js')||name==='package.json')await fs.copyFile(path.join(source,name),path.join(installed,name));
 await fs.mkdir(path.join(root,'node_modules','@mainframe'),{recursive:true});
 await fs.symlink(installed,path.join(root,'node_modules','@mainframe','activity-analytics'));
 const copied=await import(pathToFileURL(path.join(installed,'index.js')));
 const effects=[],listeners=new Map();
 const ctx={agents:{list:()=>[]},effect(fn){effects.push(fn());},on(name,fn){listeners.set(name,fn);},connection:{fetch:{register:()=>()=>{}}}};
 try {await copied.apply(ctx);await fs.access(path.join(root,'activity-analytics','intervals.sqlite'));}
 finally {await Promise.all(effects.splice(0).map(cleanup=>cleanup?.()));}
 await fs.rm(path.join(root,'node_modules','@mainframe','activity-analytics'));
 await fs.symlink(root,path.join(root,'node_modules','@mainframe','activity-analytics'));
 await assert.rejects(copied.apply(ctx),/requires an active profile directory/);
 await assert.rejects(apply(ctx),/requires an active profile directory/);
});
import { apply, createHost, inject, UI_PATH } from './index.js';

async function fixture(t, agents = []) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'activity-analytics-host-'));
  t.after(async () => {
    assert.ok(directory.startsWith(path.join(os.tmpdir(), 'activity-analytics-host-')));
    await fs.rm(directory, { recursive: true, force: true });
  });
  const listeners = new Map(), effects = [], errors = [];
  const browserPeer = {};
  let handler, tick, time = 1_000_000, stopped = 0, unregistered = false;
  const ctx = {
    agents: { list: () => agents },
    on(name, callback) { const list = listeners.get(name) || []; list.push(callback); listeners.set(name, list); },
    effect(callback) { const dispose = callback(); effects.push(dispose); return dispose; },
    connection: {
      browserPeer,
      admit(request) {
        if (request.headers.get('test-admission') === 'rejected') return { rejection: 401 };
        if (request.headers.get('test-admission') === 'api') return { peer: {} };
        return { peer: browserPeer };
      },
      fetch: { register(options) { assert.equal(options.path, UI_PATH); assert.deepEqual(options.methods, ['POST']); assert.equal(options.requestBody, 'buffered'); handler = options.fetch; return () => { unregistered = true; }; } },
    },
  };
  const store = await createHost(ctx, { directory, now: () => time, schedule: callback => { tick = callback; return () => { stopped++; }; }, reportError: () => errors.push('reported') });
  const call = async (args, options = {}) => {
    const result = await handler(new Request(`http://localhost${UI_PATH}`, { method: options.method || 'POST', headers: { 'content-type': 'application/json', 'x-activity-analytics-ui': '1', ...options.headers }, body: options.raw ?? JSON.stringify(args) }));
    return { status: result.status, headers: result.headers, value: await result.json() };
  };
  return { store, directory, call, errors, tick: () => tick(), at: n => { time = n; }, emit: (name, value) => { for (const listener of listeners.get(name) || []) listener(value); }, dispose: async () => { listeners.clear(); await Promise.all(effects.splice(0).map(effect => effect?.())); }, get stopped() { return stopped; }, get unregistered() { return unregistered; } };
}

test('apply accepts explicit profileDirectory without relying on desktop environment', async t => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'activity-analytics-profile-'));
  t.after(async()=>{assert.ok(profile.startsWith(path.join(os.tmpdir(), 'activity-analytics-profile-')));await fs.rm(profile,{recursive:true,force:true});});
  const effects=[],listeners=new Map();
  const ctx={agents:{list:()=>[]},effect(fn){effects.push(fn());},on(name,fn){listeners.set(name,fn);},connection:{fetch:{register:()=>()=>{}}}};
  await apply(ctx,{profileDirectory:profile});
  await fs.access(path.join(profile,'activity-analytics','intervals.sqlite'));
  await Promise.all(effects.splice(0).map(cleanup=>cleanup?.()));
});

test('authenticated bootstrap returns stable opaque profile-history scope without paths or content',async t=>{
  const f=await fixture(t);const first=await f.call({op:'bootstrap'}),second=await f.call({op:'bootstrap'});
  assert.equal(first.status,200);assert.match(first.value.queueScope,/^[a-f0-9]{64}$/);assert.deepEqual(first.value,second.value);
  assert.doesNotMatch(JSON.stringify(first.value),/activity-analytics-host|trackingSince|userMs/);
  assert.equal((await f.call({op:'bootstrap'},{headers:{'test-admission':'api'}})).status,403);
  await f.dispose();
});

test('Host has no tool dependency and snapshots all already-running agents without backfill', async t => {
  assert.deepEqual(inject, ['connection', 'agents']);
  const parent = { status: 'running' }, child = { status: 'running' }, idle = { status: 'idle' };
  const f = await fixture(t, [parent, child, idle]);
  f.at(1_010_000);
  const result = await f.call({ op: 'summary', start: 0, end: 2_000_000 });
  assert.equal(result.status, 200);
  assert.equal(result.value.ok, true);
  assert.equal(result.value.agentMs, 20_000);
  assert.equal(result.value.runningAgents, 2);
  assert.equal(result.value.trackingSince, 1_000_000);
  assert.equal(result.headers.get('cache-control'), 'no-store');
  f.emit('agent/status', { agent: idle, status: 'running' });
  f.at(1_015_000); f.emit('agent/disposed', { agent: child });
  f.at(1_020_000); f.emit('agent/status', { agent: parent, status: 'idle' });
  f.emit('agent/status', { agent: idle, status: 'idle' });
  const summary = (await f.call({ op: 'summary', start: 0, end: 2_000_000 })).value;
  assert.equal(summary.agentMs, 45_000);
  assert.equal(summary.runningAgents, 0);
  await f.dispose();
  assert.ok(f.stopped >= 1);
  assert.ok(f.unregistered);
});

test('owned unload closes admission, drains accepted work and persists the final active interval', async t => {
  const f = await fixture(t, [{ status: 'running' }]);
  await f.store.serial;
  f.at(1_010_000);
  const accepted = f.store.activity([{ start: 1_000_000, end: 1_005_000 }]);
  const disposing = f.dispose();
  await accepted;
  await disposing;
  assert.equal(f.stopped, 1);
  assert.equal(f.store.closed, true);
  assert.equal(f.store.active.size, 0);
  assert.throws(() => f.store.db.prepare('SELECT 1'), /closed|not open/i);
  assert.equal((await f.call({ op: 'bootstrap' })).status, 503);
  const { ActivityStore } = await import('./store.js');
  const reopened = await ActivityStore.open(f.directory, { now: () => 1_010_000 });
  try {
    const summary = await reopened.summary(0, 2_000_000);
    assert.equal(summary.agentMs, 10_000);
    assert.equal(summary.userMs, 5_000);
  } finally { await reopened.close(); }
  await f.dispose();
  assert.equal(f.stopped, 1);
});

test('owned unload reports failed final flush but still releases SQLite', async t => {
  const f = await fixture(t, [{ status: 'running' }]);
  await f.store.serial;
  f.at(1_010_000);
  f.store.persist = async () => { throw new Error('synthetic disk failure'); };
  await f.dispose();
  assert.equal(f.store.closed, true);
  assert.equal(f.store.active.size, 0);
  assert.throws(() => f.store.db.prepare('SELECT 1'), /closed|not open/i);
  assert.deepEqual(f.errors, ['reported']);
});

test('private UI admission rejects API peers, unauthenticated, and missing protection header', async t => {
  const f = await fixture(t);
  for (const headers of [{ 'test-admission': 'api' }, { 'test-admission': 'rejected' }, { 'x-activity-analytics-ui': '' }]) {
    const result = await f.call({ op: 'summary', start: 0, end: 1_000_000 }, { headers });
    assert.equal(result.status, 403);
    assert.equal(result.value.ok, false);
    assert.equal(result.value.error.code, 'FORBIDDEN');
  }
  assert.equal((await f.call({}, { headers: { 'content-type': 'text/plain' } })).status, 415);
});

test('canonical activity/summary responses union windows and accept empty summary range', async t => {
  const f = await fixture(t);
  f.at(1_025_000);
  const activity = await f.call({ op: 'activity', clientId: 'browser-one', intervals: [{ start: 1_000_000, end: 1_020_000 }] });
  assert.deepEqual(activity.value, { ok: true, accepted: 1, trackingSince: 1_000_000, persistedThrough: 1_025_000 });
  await f.call({ op: 'activity', clientId: 'browser-two', intervals: [{ start: 1_010_000, end: 1_025_000 }] });
  const summary = (await f.call({ op: 'summary', start: 1_005_000, end: 1_025_000 })).value;
  assert.equal(summary.ok, true);
  assert.equal(summary.userMs, 20_000);
  assert.equal(summary.agentMs, 0);
  assert.equal((await f.call({ op: 'summary', start: 0, end: 0 })).value.userMs, 0);
});

test('invalid operation, body, ranges, and oversized bodies return canonical errors', async t => {
  const f = await fixture(t);
  for (const args of [{ op: 'unknown' }, { op: 'summary', start: 10, end: 1 }, { op: 'activity', intervals: [{ start: 1, end: 40_000 }] }, null, []]) {
    const result = await f.call(args);
    assert.equal(result.status, 400);
    assert.equal(result.value.ok, false);
    assert.equal(result.value.error.code, 'INVALID_INPUT');
  }
  assert.equal((await f.call({}, { raw: '{broken' })).status, 400);
  assert.equal((await f.call({}, { raw: ' '.repeat(65_537) })).status, 413);
  assert.equal((await f.call({}, { headers: { 'content-length': '70000' } })).status, 413);
});

test('timer checkpoints and storage errors are contained; later requests recover', async t => {
  const f = await fixture(t, [{ status: 'running' }]);
  f.at(1_015_000); f.tick();
  await f.store.serial;
  assert.equal(f.store.db.prepare('SELECT end FROM agent_intervals').get().end, 1_015_000);
  const persist = f.store.persist.bind(f.store);
  f.store.persist = async () => { throw new Error('synthetic private detail, never return to browser'); };
  f.at(1_025_000);
  f.tick();
  await f.store.serial;
  assert.ok(f.errors.length >= 1);
  const failed = await f.call({ op: 'summary', start: 0, end: 2_000_000 });
  assert.equal(failed.status, 503);
  assert.deepEqual(failed.value, { ok: false, error: { code: 'STORAGE_FAILED', message: 'Local analytics storage is unavailable.' } });
  f.store.persist = persist;
  assert.equal((await f.call({ op: 'summary', start: 0, end: 2_000_000 })).value.agentMs, 25_000);
  await f.dispose();
  assert.equal((await f.call({ op: 'summary', start: 0, end: 2_000_000 })).status, 503);
});
