import { test } from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { VaultStore } from './index.js';

const moduleURL = new URL('./index.js', import.meta.url).href;
async function fixture(t) {
  const root = await fs.realpath(tmpdir());
  const directory = await fs.mkdtemp(path.join(root, 'mainframe-owner-synthetic-'));
  const databasePath = path.join(directory, 'vault.v2.json');
  const children = [];
  const stores = [];
  t.after(async () => {
    for (const child of children) {
      if (child.exitCode === null && child.signalCode === null) {
        const exit = once(child, 'exit'); child.kill('SIGKILL'); await exit;
      }
    }
    for (const store of stores) await store.dispose().catch(() => {});
    assert.equal(path.dirname(directory), root);
    assert.match(path.basename(directory), /^mainframe-owner-synthetic-/);
    await fs.rm(directory, { recursive: true, force: true });
  });
  const open = filesystem => { const store = new VaultStore({ databasePath }, filesystem ? { filesystem } : undefined); stores.push(store); return store; };
  const child = script => {
    const process = spawn(globalThis.process.execPath, ['--input-type=module', '-e', `import { VaultStore } from ${JSON.stringify(moduleURL)}; const databasePath = process.argv[1]; ${script}`, databasePath], { stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
    children.push(process); return process;
  };
  return { databasePath, directory, open, child };
}
const ready = async child => {
  const [message] = await Promise.race([once(child, 'message'), once(child, 'exit').then(([code]) => { throw new Error(`Synthetic child exited before ready: ${code}`); })]);
  return message;
};

test('SIGKILL owner restarts with encrypted data intact, no master password in ownership files', async t => {
  const { child, open, databasePath } = await fixture(t);
  const owner = child(`const store = new VaultStore({ databasePath }); await store.setup('synthetic-password', 'synthetic-password'); const {id} = await store.save({metadata:{name:'synthetic'},secret:'synthetic-secret'}); process.send({id});`);
  const { id } = await ready(owner);
  const exit = once(owner, 'exit'); owner.kill('SIGKILL'); await exit;
  const restarted = open();
  assert.deepEqual(await restarted.status(), { exists: true, unlocked: false });
  await restarted.unlock('synthetic-password');
  assert.equal(await restarted.internalGet(id), 'synthetic-secret');
  for (const file of await fs.readdir(`${databasePath}.node-owner`)) {
    const value = await fs.readFile(path.join(`${databasePath}.node-owner`, file), 'utf8');
    assert.equal(value.includes('synthetic-password'), false);
    assert.equal(value.includes('synthetic-secret'), false);
  }
});

for (const phase of ['gate-published', 'legacy-published', 'legacy-retired', 'gate-owner-unlinked']) {
  test(`SIGKILL at ownership boundary ${phase} permits safe restart`, async t => {
    const {child,open}=await fixture(t);
    const owner=child(`
      const {promises:fs}=await import('node:fs');
      let armed=true;
      const pause=async()=>{process.send('boundary'); await new Promise(()=>{});};
      const filesystem=new Proxy(fs,{get(target,key){
        if(key==='rename') return async(from,to)=>{
          const result=await target.rename(from,to);
          if(armed && (
            (${JSON.stringify(phase)}==='gate-published' && to===databasePath+'.node-owner') ||
            (${JSON.stringify(phase)}==='legacy-published' && to===databasePath+'.node-lock') ||
            (${JSON.stringify(phase)}==='legacy-retired' && to.startsWith(databasePath+'.node-lock.retired-'))
          )) {armed=false;await pause();}
          return result;
        };
        if(key==='unlink') return async(file)=>{
          const result=await target.unlink(file);
          if(armed && ${JSON.stringify(phase)}==='gate-owner-unlinked' && file.startsWith(databasePath+'.node-owner/')){armed=false;await pause();}
          return result;
        };
        return target[key];
      }});
      const store=new VaultStore({databasePath},{filesystem});
      await store.status(); await store.dispose();
    `);
    assert.equal(await ready(owner),'boundary');
    const exit=once(owner,'exit');owner.kill('SIGKILL');await exit;
    assert.deepEqual(await open().status(),{exists:false,unlocked:false});
  });
}

test('concurrent processes recover one crashed owner without stealing a live successor', async t => {
  const { child, databasePath } = await fixture(t);
  const crashed = child(`const store=new VaultStore({databasePath}); await store.status(); process.send('ready');`);
  await ready(crashed); const exited = once(crashed, 'exit'); crashed.kill('SIGKILL'); await exited;
  const contenders = Array.from({length: 8}, () => child(`
    const store=new VaultStore({databasePath});
    process.on('message',async message=>{if(message==='stop'){await store.dispose(); process.disconnect();}});
    try { await store.status(); process.send('owned'); }
    catch(error) { process.send(error.code); }
  `));
  const results = await Promise.all(contenders.map(ready));
  assert.equal(results.filter(value => value === 'owned').length, 1, JSON.stringify(results));
  assert.equal(results.every(value => ['owned','VAULT_BUSY'].includes(value)), true, JSON.stringify(results));
  for (const contender of contenders) contender.send('stop');
  await Promise.all(contenders.map(contender => once(contender, 'exit')));
  assert.equal(await fs.stat(`${databasePath}.node-owner`).catch(error => error.code), 'ENOENT');
});

test('live legacy owner is preserved, incomplete owner safely excluded, malformed modern owner fails closed', async t => {
  const { databasePath, open } = await fixture(t);
  const lock = `${databasePath}.node-lock`;
  await fs.mkdir(lock, { mode: 0o700 });
  const ownerFile = path.join(lock, 'owner.json');
  await fs.writeFile(ownerFile, JSON.stringify({pid:process.pid,token:'f'.repeat(64)}), { mode:0o600 });
  await assert.rejects(open().status(), {code:'VAULT_BUSY'});
  assert.equal(JSON.parse(await fs.readFile(ownerFile)).pid, process.pid);
  await fs.unlink(ownerFile);
  // Old versions could be between mkdir and write. Replace the empty directory only
  // atomically with a complete owner; the old process then fails its exclusive wx.
  const modern = open(); await modern.status(); await modern.dispose();
  await fs.mkdir(`${databasePath}.node-owner`, {mode:0o700});
  await fs.writeFile(path.join(`${databasePath}.node-owner`, 'unverified'), 'synthetic', {mode:0o600});
  await assert.rejects(open().status(), {code:'VAULT_BUSY'});
});

test('old mkdir-to-exclusive-write contender cannot activate after empty legacy gate replacement', async t => {
  const {child,open}=await fixture(t);
  // Reproduce installed 2.0.1's protocol: mkdir, lstat, exclusive owner write,
  // and deliberately no foreign cleanup if initialization fails.
  const legacy=child(`
    const {promises:fs}=await import('node:fs');
    const lock=databasePath+'.node-lock';
    await fs.mkdir(lock,{mode:0o700});await fs.lstat(lock);process.send('legacy-paused');
    await new Promise(resolve=>process.once('message',resolve));
    try{const h=await fs.open(lock+'/owner.json','wx',0o600);await h.close();process.send('unexpected-owner');}
    catch(error){process.send(error.code);}
    await new Promise(resolve=>process.once('message',resolve));
  `);
  assert.equal(await ready(legacy),'legacy-paused');
  const store=open();assert.deepEqual(await store.status(),{exists:false,unlocked:false});
  legacy.send('continue');assert.equal(await ready(legacy),'EEXIST');
  assert.deepEqual(await store.status(),{exists:false,unlocked:false});
  legacy.send('stop');await once(legacy,'exit');
});

test('transient gate release failure allows disposal retry in the same Host', async t => {
  const {databasePath,open}=await fixture(t);
  let injected=false;
  const filesystem=new Proxy(fs,{get(target,key){
    if(key==='unlink')return async file=>{
      if(!injected && file.startsWith(`${databasePath}.node-owner/`)){injected=true;throw Object.assign(new Error('synthetic gate release failure'),{code:'EIO'});}
      return target.unlink(file);
    };
    return target[key];
  }});
  const store=open(filesystem);await store.status();
  await assert.rejects(store.dispose(),/synthetic gate release failure/);
  await store.dispose();
  assert.deepEqual(await open().status(),{exists:false,unlocked:false});
});

test('retired metadata cleanup failure does not strand a live Host ownership gate', async t => {
  const {databasePath,open}=await fixture(t);
  let injected=false;
  const filesystem=new Proxy(fs,{get(target,key){
    if(key==='unlink')return async file=>{
      if(!injected && file.startsWith(`${databasePath}.node-lock.retired-`)){injected=true;throw Object.assign(new Error('synthetic retired cleanup failure'),{code:'EIO'});}
      return target.unlink(file);
    };
    return target[key];
  }});
  const store=open(filesystem);await store.status();await store.dispose();
  assert.equal(injected,true);
  assert.deepEqual(await open().status(),{exists:false,unlocked:false});
});

test('double initialization failure retains ownership for safe explicit disposal retry', async t => {
  const {directory,databasePath,open}=await fixture(t);
  let syncs=0,retirementFailed=false;
  const filesystem=new Proxy(fs,{get(target,key){
    if(key==='rename')return async (from,to)=>{
      if(!retirementFailed && from===`${databasePath}.node-lock`){retirementFailed=true;throw Object.assign(new Error('synthetic retirement failure'),{code:'EIO'});}
      return target.rename(from,to);
    };
    if(key==='open')return async (file,...args)=>{
      const handle=await target.open(file,...args);
      if(file!==directory)return handle;
      return new Proxy(handle,{get(object,property){
        if(property==='sync')return async()=>{if(++syncs===2)throw new Error('synthetic parent fsync failure');return object.sync();};
        const value=object[property];return typeof value==='function'?value.bind(object):value;
      }});
    };
    return target[key];
  }});
  const store=open(filesystem);
  await assert.rejects(store.status(),/synthetic parent fsync failure/);
  assert.equal(retirementFailed,true);
  await store.dispose();
  assert.deepEqual(await open().status(),{exists:false,unlocked:false});
});

test('parent fsync acquisition failure releases verifiable gates and allows retry', async t => {
  const {directory,databasePath,open} = await fixture(t);
  let syncs = 0;
  const filesystem = new Proxy(fs, { get(target,key) {
    if (key === 'open') return async (file,...args) => {
      const handle = await target.open(file,...args);
      if (file !== directory) return handle;
      return new Proxy(handle, {get(object,property) {
        if (property === 'sync') return async () => { if (++syncs === 2) throw new Error('synthetic parent fsync failure'); return object.sync(); };
        const value=object[property]; return typeof value==='function'?value.bind(object):value;
      }});
    };
    return target[key];
  }});
  const store=open(filesystem);
  await assert.rejects(store.status(), /synthetic parent fsync failure/);
  assert.equal(await fs.stat(`${databasePath}.node-lock`).catch(error=>error.code), 'ENOENT');
  assert.equal(await fs.stat(`${databasePath}.node-owner`).catch(error=>error.code), 'ENOENT');
  assert.deepEqual(await store.status(), {exists:false,unlocked:false});
});

test('legacy publication never leaves an empty public directory after initialization failure', async t => {
  const {databasePath,open} = await fixture(t);
  const filesystem = new Proxy(fs, { get(target,key) {
    if (key === 'open') return async (file,...args) => {
      if (String(file).includes('.node-lock.prepare-') && String(file).endsWith('owner.json')) throw new Error('synthetic write fault');
      return target.open(file,...args);
    };
    return target[key];
  }});
  await assert.rejects(open(filesystem).status(), /synthetic write fault/);
  assert.equal(await fs.stat(`${databasePath}.node-lock`).catch(error=>error.code), 'ENOENT');
  assert.deepEqual(await open().status(), {exists:false,unlocked:false});
});
