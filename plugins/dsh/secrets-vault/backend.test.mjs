import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, stat, readdir, rm } from 'node:fs/promises';
import { resolve, dirname, basename } from 'node:path';
import { tmpdir } from 'node:os';
import { VaultStore } from './vault-store.js';

async function directory(t) {
  const dir = await mkdtemp(resolve(tmpdir(), 'vault-backend-synthetic-'));
  t.after(async () => {
    assert.equal(dirname(resolve(dir)), resolve(tmpdir()));
    assert.ok(basename(dir).startsWith('vault-backend-synthetic-'));
    await rm(dir, { recursive: true });
  });
  return dir;
}
test('Node encrypted persistence, lock, wrong password and internal-only retrieval', async t => {
  const dir = await directory(t);
  const databasePath = resolve(dir, 'vault.v2.json');
  let store = new VaultStore({ databasePath });
  const password = "synthetic-test-'password-2026";
  const metadata = { label: 'SYNTHETIC-LABEL-NEVER-PLAINTEXT', provider: 'synthetic' };
  const secret = { apiKey: 'SYNTHETIC-SECRET-NEVER-PLAINTEXT' };
  try {
    assert.deepEqual(await store.status(), { exists: false, unlocked: false });
    assert.deepEqual(await readdir(dir), ['vault.v2.json.node-lock', 'vault.v2.json.node-owner']);
    const competitor = new VaultStore({ databasePath });
    try { await assert.rejects(competitor.status(), /owned|ownership lock/); } finally { await competitor.dispose(); }
    await assert.rejects(store.list(), /locked/);
    await assert.rejects(store.setup('short', 'short'), /12 characters/);
    await assert.rejects(store.setup(password, 'different'), /confirmation/);
    await assert.rejects(store.setup('synthetic-nul\u0000-password', 'synthetic-nul\u0000-password'));
    assert.deepEqual(await readdir(dir), ['vault.v2.json.node-lock', 'vault.v2.json.node-owner']);
    assert.deepEqual(await store.setup(password, password), { exists: true, unlocked: true });
    for (const invalid of [{ unknown: 'field' }, { port: true }, { port: 0 }, { port: 65536 }, { tags: 'tag' }, { tags: [123] }, { name: 12 }, { allowAgentUse: 'true' }]) {
      await assert.rejects(store.save({ metadata: invalid, secret }));
    }
    const nativeMetadata = { name: 'native', kind: 'ssh', description: 'test', host: 'example.invalid', port: 22, allowAgentUse: false, tags: ['synthetic'] };
    const native = await store.save({ metadata: nativeMetadata, secret });
    assert.deepEqual((await store.list())[0].metadata, nativeMetadata);
    await store.delete(native.id);
    const { id } = await store.save({ metadata, secret });
    const entries = await store.list();
    assert.equal(entries.length, 1);
    assert.deepEqual(entries[0].metadata, metadata);
    assert.equal(JSON.stringify(entries).includes(secret.apiKey), false);
    assert.deepEqual(await store.internalGet(id), secret);
    await store.lock();
    const bytes = await readFile(databasePath);
    assert.equal(bytes.includes(Buffer.from('SQLite format 3')), false);
    assert.equal(bytes.includes(Buffer.from(metadata.label)), false);
    assert.equal(bytes.includes(Buffer.from(secret.apiKey)), false);
    assert.equal((await stat(databasePath)).mode & 0o777, 0o600);
    assert.equal((await stat(dir)).mode & 0o777, 0o700);
    await assert.rejects(store.unlock('definitely-wrong-password'), /Unable to open/);
    assert.deepEqual(await readFile(databasePath), bytes);
    assert.deepEqual(await store.status(), { exists: true, unlocked: false });
    await store.dispose();
    store = new VaultStore({ databasePath });
    await store.unlock(password);
    assert.deepEqual(await store.internalGet(id), secret);
    await store.updateMetadata(id, { label: 'updated' });
    assert.deepEqual((await store.list())[0].metadata, { label: 'updated' });
    await store.delete(id);
    assert.deepEqual(await store.list(), []);
    await store.lock();
    await assert.rejects(store.internalGet(id), /locked/);
    assert.deepEqual((await readdir(dir)).sort(), ['vault.v2.json', 'vault.v2.json.node-lock', 'vault.v2.json.node-owner']);
  } finally { await store.dispose(); }
});

test('adapter disposal retries transient core release failure without readmitting operations', async t => {
  const databasePath=resolve(await directory(t),'vault.v2.json');
  const store=new VaultStore({databasePath});await store.status();
  const dispose=store.core.dispose.bind(store.core);let failed=false;
  store.core.dispose=async()=>{if(!failed){failed=true;throw new Error('synthetic transient release');}return dispose();};
  await assert.rejects(store.dispose(),/synthetic transient release/);
  await assert.rejects(store.status(),/unavailable/);
  await store.dispose();
  const reopened=new VaultStore({databasePath});
  try {assert.deepEqual(await reopened.status(),{exists:false,unlocked:false});} finally {await reopened.dispose();}
});

test('adapter disposal drains accepted writes, rejects new calls and releases ownership', async t => {
  const databasePath = resolve(await directory(t), 'vault.v2.json');
  const store = new VaultStore({ databasePath });
  const password = 'synthetic-queued-disposal-password';
  await store.setup(password, password);
  let release, entered;
  const gate = new Promise(resolve => { release = resolve; });
  const admitted = new Promise(resolve => { entered = resolve; });
  const save = store.core.save.bind(store.core);
  store.core.save = async value => { entered(); await gate; return save(value); };
  const pending = store.save({ metadata: { label: 'queued' }, secret: { token: 'synthetic' } });
  await admitted;
  const disposal = store.dispose();
  assert.equal(store.dispose(), disposal);
  await assert.rejects(store.status(), /unavailable/);
  release();
  const saved = await pending;
  await disposal;
  const reopened = new VaultStore({ databasePath });
  try {
    await reopened.unlock(password);
    assert.deepEqual(await reopened.internalGet(saved.id), { token: 'synthetic' });
  } finally { await reopened.dispose(); }
});
