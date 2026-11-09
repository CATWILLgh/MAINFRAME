import test from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { syncBuiltinESMExports } from 'node:module';
import { VaultStore } from './vault-store.js';
import { RecoveryStore } from './recovery-store.js';

// Isolated synthetic fixtures only. No profile, real vault, worker or credential access.
const password = 'synthetic-durability-master-password';
const nextPassword = 'synthetic-durability-replacement-password';
async function fixture(t) {
  const root = await fs.realpath(os.tmpdir());
  const directory = await fs.mkdtemp(path.join(root, 'vault-recovery-durability-synthetic-'));
  const databasePath = path.join(directory, 'synthetic.json');
  const stores = [];
  const open = () => {
    const store = new VaultStore({ databasePath }); stores.push(store);
    return { store, recovery: new RecoveryStore(store, databasePath) };
  };
  t.after(async () => {
    for (const store of stores) await store.dispose();
    assert.equal(path.dirname(path.resolve(directory)), root);
    assert.match(path.basename(directory), /^vault-recovery-durability-synthetic-/);
    await fs.rm(directory, { recursive: true });
  });
  return { ...open(), open, databasePath };
}

test('failed wrapping wipes its plaintext key buffer and generated recovery credential', async () => {
  const originalRandom = crypto.randomBytes;
  const originalCipher = crypto.createCipheriv;
  const generated = [], plaintexts = [];
  crypto.randomBytes = size => { const result = originalRandom(size); generated.push({ size, result }); return result; };
  crypto.createCipheriv = () => ({
    setAAD() {},
    update(value) { plaintexts.push(value); throw new Error('Synthetic encryption failure'); },
  });
  syncBuiltinESMExports();
  try {
    const recovery = new RecoveryStore({}, path.join(os.tmpdir(), 'unused-synthetic-durability.json'));
    await assert.rejects(recovery._new(password), /Synthetic encryption failure/);
    const credential = generated.filter(value => value.size === 32)[1]?.result;
    assert.ok(credential);
    assert.equal(credential.every(value => value === 0), true);
    assert.equal(plaintexts.length, 1);
    assert.equal(plaintexts[0].every(value => value === 0), true);
  } finally {
    crypto.randomBytes = originalRandom;
    crypto.createCipheriv = originalCipher;
    syncBuiltinESMExports();
  }
});

// Patching the built-in fs promises object is confined to this sequential test file.
// The real adapter/core use it too, unlike the FakeStore rekey-failure tests.
for (const target of ['sidecar', 'database', 'bridge-cleanup']) {
  for (const after of [false, true]) {
    test(`real core recovery resumes after ${target} rename ${after ? 'completed then failed' : 'failed before commit'}`, async t => {
      let { store, recovery, open, databasePath } = await fixture(t);
      const issued = await recovery.setup(password, password);
      const { id } = await store.save({ metadata: { name: 'synthetic durability fixture' }, secret: 'SYNTHETIC-DURABILITY-SECRET' });
      const originalRename = fs.rename;
      let sidecarRenames = 0, hit = false;
      fs.rename = async function(from, to) {
        const sidecar = to === recovery.sidecarPath;
        if (sidecar) sidecarRenames++;
        const selected = target === 'database' ? to === databasePath : sidecar && sidecarRenames === (target === 'bridge-cleanup' ? 2 : 1);
        if (selected && !hit) {
          hit = true;
          if (after) await originalRename.call(fs, from, to);
          throw new Error('Synthetic interrupted rename');
        }
        return originalRename.call(fs, from, to);
      };
      try { await assert.rejects(recovery.recover(issued.recoveryKey, nextPassword, nextPassword)); }
      finally { fs.rename = originalRename; }
      assert.equal(hit, true);
      if (target === 'database') await assert.rejects(store.internalGet(id), error => error.code === 'VAULT_UNCERTAIN_COMMIT');
      await store.dispose();
      ({ store, recovery } = open());
      const oldStillAuthoritative = target === 'sidecar' && !after;
      const activePassword = oldStillAuthoritative ? password : nextPassword;
      await recovery.unlock(activePassword);
      assert.equal(await store.internalGet(id), 'SYNTHETIC-DURABILITY-SECRET');
      assert.equal(JSON.parse(await fs.readFile(recovery.sidecarPath, 'utf8')).migration, undefined);
      await recovery.lock();
      await assert.rejects(recovery.unlock(oldStillAuthoritative ? nextPassword : password));
      if (!oldStillAuthoritative) await assert.rejects(recovery.recover(issued.recoveryKey, password, password));
      await recovery.unlock(activePassword);
      const replacement = await recovery.rotate(activePassword);
      assert.match(replacement.recoveryKey, /^dsh-recovery-v1-/);
      assert.equal(await store.internalGet(id), 'SYNTHETIC-DURABILITY-SECRET');
    });
  }
}
