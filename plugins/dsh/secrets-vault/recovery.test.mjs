import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { RecoveryStore } from './recovery-store.js';
import { VaultStore } from './vault-store.js';

// Synthetic worker only. Never reads a user's vault, keychain, or credential DB.
class FakeStore {
  constructor() { this.key = null; this.unlocked = false; this.rekeys = 0; }
  async status() { return { exists: this.key !== null, unlocked: this.unlocked }; }
  async setup(key, confirmation) { assert.equal(key, confirmation); if (this.key) throw Error('exists'); this.key = key; this.unlocked = true; }
  async lock() { this.unlocked = false; return this.status(); }
  async unlock(key) { if (this.key !== key) throw Error('bad key'); this.unlocked = true; return this.status(); }
  async rekey(key) {
    assert.equal(this.unlocked, true);
    if (this.failBeforeRekey) { this.failBeforeRekey = false; throw Error('simulated crash before rekey'); }
    this.key = key; this.rekeys++;
    if (this.failAfterRekey) { this.failAfterRekey = false; throw Error('simulated crash after rekey'); }
  }
}
async function fixture(t) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'dsh-recovery-synthetic-'));
  await fs.chmod(directory, 0o700);
  const disposals = [];
  t.after(async () => {
    for (const dispose of disposals) await dispose();
    // Resolve and constrain the test-owned target before deleting it.
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(directory).startsWith('dsh-recovery-synthetic-'));
    await fs.rm(directory, { recursive: true });
  });
  const store = new FakeStore();
  const databasePath = path.join(directory, 'synthetic.db');
  return { directory, store, recovery: new RecoveryStore(store, databasePath), databasePath, disposals };
}
const password = 'synthetic master password';
const nextPassword = 'synthetic replacement password';

test('setup, private issuance, password unlock and single-use recovery rotate DB key', async t => {
  const { recovery, store } = await fixture(t);
  const issued = await recovery.setup(password, password);
  assert.match(issued.recoveryKey, /^dsh-recovery-v1-/);
  assert.deepEqual(Object.keys(await recovery.status()).sort(), ['exists', 'recoveryAvailable', 'unlocked']);
  const oldKey = store.key;
  await recovery.lock();
  await assert.rejects(recovery.unlock('incorrect master'));
  await recovery.unlock(password);
  const replacement = await recovery.recover(issued.recoveryKey, nextPassword, nextPassword);
  assert.notEqual(replacement.recoveryKey, issued.recoveryKey);
  assert.notEqual(store.key, oldKey);
  await assert.rejects(recovery.recover(issued.recoveryKey, password, password));
  await assert.rejects(recovery.unlock(password));
  await recovery.unlock(nextPassword);
  await recovery.recover(replacement.recoveryKey, password, password);
});

test('legacy enable requires fresh master authentication, and deletes migration bridge', async t => {
  const { recovery, store } = await fixture(t);
  await store.setup(password, password);
  await assert.rejects(recovery.enable('wrong password'));
  assert.equal((await recovery.status()).recoveryAvailable, false);
  await store.unlock(password);
  const issued = await recovery.enable(password);
  assert.equal(store.rekeys, 1);
  const raw = await fs.readFile(recovery.sidecarPath, 'utf8');
  assert.ok(!raw.includes(password));
  assert.ok(!raw.includes(issued.recoveryKey));
  assert.ok(!raw.includes(store.key));
  assert.equal(JSON.parse(raw).migration, undefined);
  assert.equal((await fs.stat(recovery.sidecarPath)).mode & 0o777, 0o600);
  await recovery.unlock(password);
});

for (const point of ['failBeforeRekey', 'failAfterRekey']) {
  test(`legacy migration resumes after ${point}`, async t => {
    const { recovery, store, databasePath } = await fixture(t);
    await store.setup(password, password);
    store[point] = true;
    await assert.rejects(recovery.enable(password));
    assert.ok(JSON.parse(await fs.readFile(recovery.sidecarPath, 'utf8')).migration);
    const restarted = new RecoveryStore(store, databasePath);
    await restarted.unlock(password);
    assert.equal(JSON.parse(await fs.readFile(recovery.sidecarPath, 'utf8')).migration, undefined);
    assert.notEqual(store.key, password);
  });
  test(`recovery resumes with replacement password after ${point}`, async t => {
    const { recovery, store, databasePath } = await fixture(t);
    const issued = await recovery.setup(password, password);
    store[point] = true;
    await assert.rejects(recovery.recover(issued.recoveryKey, nextPassword, nextPassword));
    const restarted = new RecoveryStore(store, databasePath);
    await assert.rejects(restarted.unlock(password));
    await restarted.unlock(nextPassword);
    await assert.rejects(restarted.recover(issued.recoveryKey, password, password));
    // A lost response must be handled by authenticated regeneration, never replay.
    const replacement = await restarted.rotate(nextPassword);
    await restarted.recover(replacement.recoveryKey, password, password);
  });
}

test('tampering and unsupported sidecar fail closed instead of legacy fallback', async t => {
  const { recovery } = await fixture(t);
  await recovery.setup(password, password);
  const original = await fs.readFile(recovery.sidecarPath, 'utf8');
  const changed = JSON.parse(original); changed.generation++;
  await fs.writeFile(recovery.sidecarPath, JSON.stringify(changed), { mode: 0o600 });
  await assert.rejects(recovery.unlock(password));
  changed.version = 999;
  await fs.writeFile(recovery.sidecarPath, JSON.stringify(changed), { mode: 0o600 });
  await assert.rejects(recovery.unlock(password));
});

test('missing DB after interrupted setup preserves envelope and refuses overwrite', async t => {
  const { recovery, store } = await fixture(t);
  store.setup = async () => { throw Error('simulated setup failure'); };
  await assert.rejects(recovery.setup(password, password));
  const before = await fs.readFile(recovery.sidecarPath, 'utf8');
  await assert.rejects(recovery.setup(nextPassword, nextPassword));
  assert.equal(await fs.readFile(recovery.sidecarPath, 'utf8'), before);
});

test('real Node synthetic recovery enable, restart and key rotation', async t => {
  const { databasePath, disposals } = await fixture(t);
  let store = new VaultStore({ databasePath });
  disposals.push(() => store.dispose());
  await store.setup(password, password);
  const secret = { token: 'SYNTHETIC-RECOVERY-INTEGRATION-NOT-A-CREDENTIAL' };
  const { id } = await store.save({ metadata: { name: 'synthetic recovery fixture' }, secret });
  let recovery = new RecoveryStore(store, databasePath);
  const issued = await recovery.enable(password);
  assert.deepEqual(await store.internalGet(id), secret);
  await store.dispose();
  store = new VaultStore({ databasePath });
  recovery = new RecoveryStore(store, databasePath);
  await assert.rejects(store.unlock(password));
  await recovery.unlock(password);
  const replacement = await recovery.recover(issued.recoveryKey, nextPassword, nextPassword);
  assert.deepEqual(await store.internalGet(id), secret);
  await assert.rejects(recovery.recover(issued.recoveryKey, password, password));
  await recovery.lock();
  await recovery.unlock(nextPassword);
  assert.deepEqual(await store.internalGet(id), secret);
  await recovery.recover(replacement.recoveryKey, password, password);
  assert.deepEqual(await store.internalGet(id), secret);
  const bytes = await fs.readFile(databasePath);
  assert.equal(bytes.includes(Buffer.from(secret.token)), false);
});

test('symlink sidecar is rejected', async t => {
  const { recovery, directory } = await fixture(t);
  const target = path.join(directory, 'synthetic-target');
  await fs.writeFile(target, '{}', { mode: 0o600 });
  await fs.symlink(target, recovery.sidecarPath);
  await assert.rejects(recovery.status());
  await assert.rejects(recovery.setup(password, password));
});
