import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, stat, readdir, rm } from 'node:fs/promises';
import { accessSync, constants } from 'node:fs';
import { resolve, dirname, basename } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { VaultStore } from './vault-store.js';

const python = process.env.MAINFRAME_TEST_VAULT_PYTHON || fileURLToPath(new URL('./runtime/bin/python3.12', import.meta.url));
function requireRuntime() {
  try { accessSync(python, constants.X_OK); }
  catch { throw new Error('Vault integration tests require an executable bundled runtime; stage runtime/bin/python3.12 or set MAINFRAME_TEST_VAULT_PYTHON to a verified Python with sqlcipher3.'); }
}

test('SQLCipher encrypted persistence, lock, wrong password and internal-only retrieval', async t => {
  requireRuntime();
  const dir = await mkdtemp(resolve(tmpdir(), 'vault-backend-synthetic-'));
  t.after(async () => {
    assert.equal(dirname(resolve(dir)), resolve(tmpdir()));
    assert.ok(basename(dir).startsWith('vault-backend-synthetic-'));
    await rm(dir, { recursive: true });
  });
  const databasePath = resolve(dir, 'vault.db');
  let store = new VaultStore({ python, databasePath });
  const password = "synthetic-test-'password-2026";
  const metadata = { label: 'SYNTHETIC-LABEL-NEVER-PLAINTEXT', provider: 'synthetic' };
  const secret = { apiKey: 'SYNTHETIC-SECRET-NEVER-PLAINTEXT' };
  try {
    assert.deepEqual(await store.status(), { exists: false, unlocked: false });
    assert.deepEqual(await readdir(dir), ['vault.db.lock']);
    const competitor=new VaultStore({python,databasePath});
    try {await assert.rejects(competitor.status(),/unavailable/);} finally {await competitor.dispose();}
    await assert.rejects(store.list(), /locked/);
    await assert.rejects(store.setup('short', 'short'), /12 characters/);
    await assert.rejects(store.setup(password, 'different'), /confirmation/);
    await assert.rejects(store.setup('synthetic-nul\u0000-password', 'synthetic-nul\u0000-password'));
    assert.deepEqual(await readdir(dir), ['vault.db.lock']);
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
    store = new VaultStore({ python, databasePath });
    await store.unlock(password);
    assert.deepEqual(await store.internalGet(id), secret);
    await store.updateMetadata(id, { label: 'updated' });
    assert.deepEqual((await store.list())[0].metadata, { label: 'updated' });
    await store.delete(id);
    assert.deepEqual(await store.list(), []);
    await store.lock();
    await assert.rejects(store.internalGet(id), /locked/);
    assert.deepEqual((await readdir(dir)).sort(), ['vault.db', 'vault.db.lock']);
  } finally { await store.dispose(); }
});
