import { test } from 'node:test';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { scrypt, randomBytes, createCipheriv } from 'node:crypto';
import { promisify } from 'node:util';
import { VaultStore, MAX_FILE_BYTES, MAX_RECORDS } from './index.js';

const PASSWORD = 'synthetic-password-2026';
async function fixture(t, filesystem) {
  const directory = await fs.mkdtemp(path.join(await fs.realpath(tmpdir()), 'mainframe-node-vault-synthetic-'));
  await fs.chmod(directory, 0o700);
  const databasePath = path.join(directory, 'vault.v2.json');
  const stores = [];
  const open = (options = filesystem) => {
    const store = new VaultStore({ databasePath }, options ? { filesystem: options } : undefined);
    stores.push(store); return store;
  };
  t.after(async () => {
    for (const store of stores) await store.dispose().catch(() => {});
    assert.equal(path.dirname(directory), await fs.realpath(tmpdir()));
    assert.match(path.basename(directory), /^mainframe-node-vault-synthetic-/);
    await fs.rm(directory, { recursive: true, force: true });
  });
  return { directory, databasePath, store: open(), open };
}
const code = expected => error => error.code === expected;

// All fixtures and values in this suite are synthetic, never actual credential paths.
test('encrypted persistence, restart, revisions, output isolation and rekey', async t => {
  const { store, databasePath, directory, open } = await fixture(t);
  assert.deepEqual(await store.status(), { exists: false, unlocked: false });
  await assert.rejects(store.list(), /locked/);
  assert.deepEqual(await store.setup(PASSWORD, PASSWORD), { exists: true, unlocked: true });
  const metadata = { label: 'SYNTHETIC-METADATA-HIDDEN', allowAgentUse: false, tags: ['test'] };
  const secret = { apiKey: 'SYNTHETIC-SECRET-HIDDEN', nested: { value: true } };
  const { id } = await store.save({ metadata, secret });
  let rows = await store.list();
  assert.equal(rows[0].revision, 1); assert.equal(rows[0].id, id);
  assert.deepEqual(rows[0].metadata, metadata);
  assert.equal(JSON.stringify(rows).includes(secret.apiKey), false);
  rows[0].metadata.label = 'changed output';
  const output = await store.internalGet(id); output.nested.value = false;
  assert.deepEqual(await store.internalGet(id), secret);
  assert.deepEqual((await store.list())[0].metadata, metadata);
  await store.updateMetadata(id, { name: 'renamed' }, 1);
  assert.equal((await store.list())[0].revision, 2);
  await assert.rejects(store.save({ id, metadata, secret, expectedRevision: 1 }), code('VAULT_CONFLICT'));
  await store.lock();
  const bytes = await fs.readFile(databasePath);
  for (const text of [secret.apiKey, 'renamed', 'SQLite format 3']) assert.equal(bytes.includes(Buffer.from(text)), false);
  assert.ok(bytes.length < MAX_FILE_BYTES); assert.equal(MAX_RECORDS, 4096);
  if (process.platform !== 'win32') {
    assert.equal((await fs.stat(databasePath)).mode & 0o777, 0o600);
    assert.equal((await fs.stat(directory)).mode & 0o777, 0o700);
  }
  await assert.rejects(store.unlock('synthetic-wrong-password'), code('VAULT_AUTHENTICATION_FAILED'));
  assert.deepEqual(await fs.readFile(databasePath), bytes);
  assert.deepEqual(await store.status(), { exists: true, unlocked: false });
  await store.unlock(PASSWORD);
  await store.rekey('synthetic-new-password-2026');
  await store.dispose();
  const restarted = open();
  await assert.rejects(restarted.unlock(PASSWORD), code('VAULT_AUTHENTICATION_FAILED'));
  await restarted.unlock('synthetic-new-password-2026');
  assert.deepEqual(await restarted.internalGet(id), secret);
  await restarted.delete(id, 2);
  assert.deepEqual(await restarted.list(), []);
  assert.deepEqual(await restarted.delete(id), { deleted: true });
});

test('metadata discovery pages over 100 records, searches metadata only, and uses current-view offsets', async t => {
  const {store}=await fixture(t);await store.setup(PASSWORD,PASSWORD);
  for(let i=0;i<105;i++)await store.save({metadata:{name:`Entry ${i}`,tags:[i%2?'Odd':'Even']},secret:'PRIVATE-SEARCH-NEEDLE'});
  const full=await store.list(),first=await store.listPage();
  assert.deepEqual(first.records,full.slice(0,100));assert.equal(first.nextOffset,100);assert.equal(first.total,105);
  assert.deepEqual((await store.listPage({offset:100})).records,full.slice(100));
  assert.deepEqual(await store.listPage({offset:105}),{records:[],total:105,nextOffset:null});
  const filtered=await store.listPage({query:'eVeN',limit:7});assert.equal(filtered.records.length,7);assert.equal(filtered.total,53);assert.equal(filtered.nextOffset,7);
  assert.equal((await store.listPage({query:'PRIVATE-SEARCH-NEEDLE'})).total,0);
  const record=await store.getMetadata(full[0].id);record.metadata.name='output mutation';assert.notEqual((await store.getMetadata(full[0].id)).metadata.name,'output mutation');
  assert.equal(await store.getMetadata('absent'),undefined);
  await store.delete(full[0].id);const changed=await store.listPage({offset:100});assert.equal(changed.total,104);assert.deepEqual(changed.records,(await store.list()).slice(100));
  for(const options of [{offset:-1},{offset:1.5},{offset:4097},{limit:0},{limit:101},{limit:1.5},{query:5},{query:'x'.repeat(257)}])await assert.rejects(store.listPage(options),code('VAULT_INVALID_ARGUMENTS'));
});

test('serialization, optimistic update/delete conflicts, and input mutation races', async t => {
  const { store } = await fixture(t);
  const setup = store.setup(PASSWORD, PASSWORD);
  const metadata = { label: 'admitted', tags: ['original'] };
  const secret = { value: 'original' };
  const save = store.save({ metadata, secret });
  metadata.label = 'mutated'; metadata.tags[0] = 'mutated'; secret.value = 'mutated';
  const listing = store.list();
  await setup;
  const { id } = await save;
  assert.deepEqual((await listing)[0].metadata, { label: 'admitted', tags: ['original'] });
  assert.deepEqual(await store.internalGet(id), { value: 'original' });
  const next = { label: 'snapshot' };
  const one = store.updateMetadata(id, next, 1);
  next.label = 'mutation';
  const two = store.updateMetadata(id, { label: 'loser' }, 1);
  const three = store.delete(id, 1);
  await one;
  await assert.rejects(two, code('VAULT_CONFLICT'));
  await assert.rejects(three, code('VAULT_CONFLICT'));
  assert.equal((await store.list())[0].metadata.label, 'snapshot');
  await Promise.all(Array.from({ length: 15 }, (_, index) => store.save({ metadata: { name: String(index) }, secret: `synthetic-${index}` })));
  assert.equal((await store.list()).length, 16);
  assert.equal((await store.list()).every(row => Number.isSafeInteger(row.revision)), true);
});

test('dispose rejects admission immediately, drains work, and releases ownership', async t => {
  const { store, open } = await fixture(t);
  const setup = store.setup(PASSWORD, PASSWORD);
  const saved = store.save({ metadata: {}, secret: 'synthetic-drained' });
  const disposal = store.dispose();
  assert.equal(store.dispose(), disposal);
  await assert.rejects(store.status(), code('VAULT_DISPOSED'));
  await assert.rejects(store.save({ metadata: {}, secret: 'synthetic-late' }), code('VAULT_DISPOSED'));
  await setup; const { id } = await saved; await disposal;
  const restarted = open(); await restarted.unlock(PASSWORD);
  assert.equal(await restarted.internalGet(id), 'synthetic-drained');
});

test('owner rejection in-process/cross-process and dead legacy owner recovery', async t => {
  const { store, open, directory, databasePath } = await fixture(t);
  await store.status();
  const second = open();
  await assert.rejects(second.status(), code('VAULT_BUSY'));
  const child = spawn(process.execPath, ['--input-type=module', '-e', `
    import { VaultStore } from ${JSON.stringify(new URL('./index.js', import.meta.url).href)};
    const store = new VaultStore({databasePath: process.argv[1]});
    try { await store.status(); process.exitCode = 2; }
    catch (error) { if(error.code !== 'VAULT_BUSY') { console.error(error.code); process.exitCode = 3; } }
    finally { await store.dispose(); }
  `, databasePath], { stdio: ['ignore', 'pipe', 'pipe'] });
  let errors = ''; child.stderr.on('data', chunk => { errors += chunk; });
  const exit = await new Promise((resolve, reject) => { child.once('error', reject); child.once('exit', resolve); });
  assert.equal(exit, 0, errors);
  await store.dispose();
  await fs.mkdir(`${databasePath}.node-lock`, { mode: 0o700 });
  await fs.writeFile(path.join(`${databasePath}.node-lock`, 'owner.json'), JSON.stringify({ pid: 99999999, token: 'a'.repeat(64) }), { mode: 0o600 });
  assert.deepEqual(await second.status(), { exists: false, unlocked: false });
  assert.equal(JSON.parse(await fs.readFile(path.join(`${databasePath}.node-lock`, 'owner.json'))).pid, process.pid);
});

test('path aliases use one canonical owner; historical flock file is untouched', async t => {
  const { store, directory, databasePath } = await fixture(t);
  await fs.writeFile(`${databasePath}.lock`, 'synthetic-old-flock', { mode: 0o600 });
  await store.status();
  const alias = new VaultStore({ databasePath: path.join(directory, '.', 'vault.v2.json') });
  try { await assert.rejects(alias.status(), code('VAULT_BUSY')); } finally { await alias.dispose(); }
  await store.dispose();
  assert.equal(await fs.readFile(`${databasePath}.lock`, 'utf8'), 'synthetic-old-flock');
});

test('wrong password and tampered authenticated fields fail closed without writes', async t => {
  const { store, databasePath } = await fixture(t);
  await store.setup(PASSWORD, PASSWORD);
  await store.save({ metadata: { name: 'synthetic' }, secret: 'synthetic-value' });
  await store.lock();
  const bytes = await fs.readFile(databasePath, 'utf8');
  const magic = bytes.slice(0, bytes.indexOf('\n') + 1);
  const original = JSON.parse(bytes.slice(magic.length));
  for (const field of ['id', 'salt', 'nonce', 'ciphertext', 'tag']) {
    const changed = structuredClone(original);
    const buffer = Buffer.from(changed[field], 'base64url'); buffer[0] ^= 1; changed[field] = buffer.toString('base64url');
    const modified = magic + JSON.stringify(changed);
    await fs.writeFile(databasePath, modified, { mode: 0o600 });
    await assert.rejects(store.unlock(PASSWORD), code('VAULT_AUTHENTICATION_FAILED'));
    assert.deepEqual(await store.status(), { exists: true, unlocked: false });
    assert.equal(await fs.readFile(databasePath, 'utf8'), modified);
  }
  for (const patch of [{ version: 99 }, { kdf: { ...original.kdf, N: 2 ** 30 } }, { tag: 'invalid+' }, { extra: true }, { salt: '' }]) {
    await fs.writeFile(databasePath, magic + JSON.stringify({ ...original, ...patch }));
    await assert.rejects(store.unlock(PASSWORD), code('VAULT_AUTHENTICATION_FAILED'));
  }
  await fs.writeFile(databasePath, bytes);
  await store.unlock(PASSWORD);
});

test('legacy/unknown files and oversized input are never overwritten', async t => {
  const { store, databasePath } = await fixture(t);
  const legacy = Buffer.from('SQLite format 3\0SYNTHETIC-ONLY');
  await fs.writeFile(databasePath, legacy, { mode: 0o600 });
  await assert.rejects(store.unlock(PASSWORD), code('LEGACY_VAULT_FORMAT'));
  await assert.rejects(store.setup(PASSWORD, PASSWORD), /already exists/);
  assert.deepEqual(await fs.readFile(databasePath), legacy);
  const handle = await fs.open(databasePath, 'r+');
  await handle.truncate(MAX_FILE_BYTES + 1); await handle.close();
  await assert.rejects(store.unlock(PASSWORD), code('VAULT_TOO_LARGE'));
  assert.equal((await fs.stat(databasePath)).size, MAX_FILE_BYTES + 1);
});

test('validation rejects invalid passwords, metadata, secrets, executable objects and revisions', async t => {
  const { store } = await fixture(t);
  for (const password of ['', 'short', 'synthetic-nul\0-password', 'a'.repeat(4097)]) await assert.rejects(store.setup(password, password));
  await assert.rejects(store.setup(PASSWORD, 'different'), /confirmation/);
  await store.setup(PASSWORD, PASSWORD);
  for (const value of [{ unknown: true }, { name: 1 }, { notes: 'x'.repeat(8193) }, { port: true }, { port: 0 }, { port: 65536 }, { allowAgentUse: 'true' }, { tags: [1] }, { tags: Array(101).fill('x') }, { label: '\0' }]) await assert.rejects(store.save({ metadata: value, secret: 'synthetic' }));
  const object = { get hidden() { throw new Error('getter must never execute'); } };
  const circular = {}; circular.self = circular;
  for (const value of [null, true, 1, [], new Date(), { toJSON() { throw new Error('must never execute'); } }, circular, object, { value: undefined }, { value: NaN }, { value: BigInt(1) }]) await assert.rejects(store.save({ metadata: {}, secret: value }));
  await assert.rejects(store.save({ metadata: {}, secret: 'x'.repeat(1048576) }), /too large/);
  await assert.rejects(store.save({ metadata: {}, secret: 'synthetic', expectedRevision: 1 }));
  const { id } = await store.save({ metadata: { name: 'valid', host: 'example.invalid', port: 22, allowAgentUse: true }, secret: { '__proto__': null, nested: ['safe', null, false] } });
  for (const revision of [0, -1, 1.5, NaN, '1']) await assert.rejects(store.delete(id, revision));
  await assert.rejects(store.internalGet('missing'), code('VAULT_NOT_FOUND'));
  assert.equal((await store.list()).length, 1);
});

test('precommit failure preserves old memory/disk; uncertain commit requires reopen', async t => {
  let fault;
  const filesystem = new Proxy(fs, { get(target, key) {
    if (key === 'open') return async (...args) => {
      const handle = await target.open(...args);
      if (fault === 'file-sync' && String(args[0]).endsWith('.tmp')) return new Proxy(handle, { get(h, method) { if (method === 'sync') return async () => { throw new Error('synthetic fsync failure'); }; const value = h[method]; return typeof value === 'function' ? value.bind(h) : value; } });
      if (fault === 'directory-sync' && args[0] === directory) return new Proxy(handle, { get(h, method) { if (method === 'sync') return async () => { throw new Error('synthetic directory fsync failure'); }; const value = h[method]; return typeof value === 'function' ? value.bind(h) : value; } });
      return handle;
    };
    if (key === 'rename') return async (...args) => { if (fault === 'rename') throw new Error('synthetic ambiguous rename'); return target.rename(...args); };
    return target[key];
  } });
  const { store, directory, databasePath, open } = await fixture(t, filesystem);
  await store.setup(PASSWORD, PASSWORD);
  const { id } = await store.save({ metadata: { label: 'old' }, secret: 'synthetic-old' });
  const bytes = await fs.readFile(databasePath);
  fault = 'file-sync';
  await assert.rejects(store.updateMetadata(id, { label: 'uncommitted' }), /synthetic fsync/);
  assert.deepEqual(await fs.readFile(databasePath), bytes);
  assert.equal((await store.list())[0].metadata.label, 'old');
  assert.equal((await fs.readdir(directory)).some(name => name.endsWith('.tmp')), false);
  fault = 'rename';
  await assert.rejects(store.updateMetadata(id, { label: 'ambiguous' }), code('VAULT_UNCERTAIN_COMMIT'));
  await assert.rejects(store.internalGet(id), code('VAULT_UNCERTAIN_COMMIT'));
  fault = undefined; await store.dispose();
  const restarted = open(fs); await restarted.unlock(PASSWORD);
  assert.equal((await restarted.list())[0].metadata.label, 'old');
  await restarted.dispose();
  if (process.platform !== 'win32') {
    const next = open(filesystem); await next.unlock(PASSWORD);
    fault = 'directory-sync';
    await assert.rejects(next.updateMetadata(id, { label: 'committed-but-not-durable' }), code('VAULT_UNCERTAIN_COMMIT'));
    fault = undefined; await next.dispose();
    const after = open(fs); await after.unlock(PASSWORD);
    assert.equal((await after.list())[0].metadata.label, 'committed-but-not-durable');
  }
});

test('authenticated but invalid plaintext is rejected, including duplicate ids and record limits', async t => {
  const { store, databasePath } = await fixture(t);
  await store.setup(PASSWORD, PASSWORD);
  const { id } = await store.save({ metadata: {}, secret: 'synthetic', id: undefined, expectedRevision: undefined });
  const row = { ...(await store.list())[0], secret: 'synthetic' };
  await store.lock();
  const bytes = await fs.readFile(databasePath, 'utf8');
  const magic = bytes.slice(0, bytes.indexOf('\n') + 1);
  const document = JSON.parse(bytes.slice(magic.length));
  const key = await promisify(scrypt)(PASSWORD, Buffer.from(document.salt, 'base64url'), 32, document.kdf);
  try {
    for (const payload of [
      { version: 1, records: [row, row] },
      { version: 1, records: [{ ...row, revision: 0 }] },
      { version: 1, records: [{ ...row, secret: [] }] },
      { version: 1, records: [{ ...row, metadata: { unknown: true } }] },
      { version: 1, records: [{ ...row, created: 'not a date' }] },
      { version: 1, records: Array(MAX_RECORDS + 1).fill(row) },
      { version: 1, records: [row], extra: true },
    ]) {
      const nonce = randomBytes(12);
      const cipher = createCipheriv('aes-256-gcm', key, nonce);
      cipher.setAAD(Buffer.from(JSON.stringify({ version: document.version, id: document.id, kdf: document.kdf, salt: document.salt })));
      const ciphertext = Buffer.concat([cipher.update(JSON.stringify(payload)), cipher.final()]);
      const next = { ...document, nonce: nonce.toString('base64url'), ciphertext: ciphertext.toString('base64url'), tag: cipher.getAuthTag().toString('base64url') };
      await fs.writeFile(databasePath, magic + JSON.stringify(next));
      await assert.rejects(store.unlock(PASSWORD), code('VAULT_AUTHENTICATION_FAILED'));
    }
  } finally { key.fill(0); }
  await fs.writeFile(databasePath, bytes); await store.unlock(PASSWORD);
  assert.equal(await store.internalGet(id), 'synthetic');
});

test('external replacement is preserved and fails closed instead of being overwritten', async t => {
  const { store, databasePath } = await fixture(t);
  await store.setup(PASSWORD, PASSWORD);
  const { id } = await store.save({ metadata: { name: 'original' }, secret: 'synthetic' });
  const replacement = 'synthetic-external-replacement';
  await fs.writeFile(databasePath, replacement, { mode: 0o600 });
  await assert.rejects(store.updateMetadata(id, { name: 'lost-update' }), code('VAULT_EXTERNAL_CHANGE'));
  assert.equal(await fs.readFile(databasePath, 'utf8'), replacement);
  await assert.rejects(store.list(), code('VAULT_UNCERTAIN_COMMIT'));
});

test('symlinks, unsafe permissions, hard links and ownership replacement are rejected', { skip: process.platform === 'win32' }, async t => {
  const { store, directory, databasePath, open } = await fixture(t);
  const target = path.join(directory, 'synthetic-target');
  await fs.writeFile(target, 'synthetic-untouched', { mode: 0o600 });
  await fs.symlink(target, databasePath);
  await assert.rejects(store.status(), code('UNSAFE_VAULT_PATH'));
  await assert.rejects(store.setup(PASSWORD, PASSWORD), code('UNSAFE_VAULT_PATH'));
  assert.equal(await fs.readFile(target, 'utf8'), 'synthetic-untouched');
  // Checked fixture path, only remove the synthetic symlink created above.
  assert.equal(path.dirname(databasePath), directory); await fs.unlink(databasePath);
  await fs.link(target, databasePath);
  await assert.rejects(store.status(), code('UNSAFE_VAULT_PATH'));
  await fs.unlink(databasePath);
  await fs.writeFile(databasePath, 'synthetic', { mode: 0o644 });
  await assert.rejects(store.status(), code('UNSAFE_VAULT_PATH'));
  await fs.chmod(databasePath, 0o600); await store.dispose();
  const aliasDirectory = path.join(directory, 'synthetic-directory-link');
  await fs.symlink(directory, aliasDirectory);
  const linked = new VaultStore({ databasePath: path.join(aliasDirectory, 'other.json') });
  try { await assert.rejects(linked.status(), code('UNSAFE_VAULT_PATH')); } finally { await linked.dispose(); }
  await fs.chmod(directory, 0o755);
  const unsafe = open(); await assert.rejects(unsafe.status(), code('UNSAFE_VAULT_PATH'));
  await fs.chmod(directory, 0o700);
  const owner = open(); await owner.status();
  const lock = `${databasePath}.node-lock`;
  const ownerPath = path.join(lock, 'owner.json');
  await fs.writeFile(ownerPath, JSON.stringify({ pid: process.pid, token: 'synthetic-replaced-owner' }), { mode: 0o600 });
  await assert.rejects(owner.list(), code('VAULT_OWNERSHIP_LOST'));
  await assert.rejects(owner.dispose(), code('VAULT_OWNERSHIP_LOST'));
  assert.equal(JSON.parse(await fs.readFile(ownerPath, 'utf8')).token, 'synthetic-replaced-owner');
});
