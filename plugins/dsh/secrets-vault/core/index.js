import { randomBytes, randomUUID, scrypt, createCipheriv, createDecipheriv, createHash } from 'node:crypto';
import { promises as fs, constants } from 'node:fs';
import path from 'node:path';
import { promisify } from 'node:util';
import { TextDecoder } from 'node:util';

const derive = promisify(scrypt);
const MAGIC = 'MAINFRAME-VAULT-2\n';
const KDF = Object.freeze({ name: 'scrypt', N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
export const MAX_FILE_BYTES = 32 * 1024 * 1024;
export const MAX_RECORDS = 4096;
const owners = new Map();
const decoder = new TextDecoder('utf-8', { fatal: true });
const strings = new Set(['label', 'provider', 'type', 'notes', 'username', 'url', 'name', 'kind', 'description', 'host']);
const fail = (message, code = 'VAULT_ERROR', reason) => Object.assign(new Error(message), { code, ...(reason ? { reason } : {}) });
const authFailure = () => fail('Unable to open vault. Check password and vault file.', 'VAULT_AUTHENTICATION_FAILED');
const plain = value => value !== null && typeof value === 'object' && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const exact = (value, keys) => plain(value) && Object.keys(value).sort().join(',') === [...keys].sort().join(',');
const b64 = bytes => bytes.toString('base64url');
function unb64(value, size, max = size) {
  if (typeof value !== 'string' || value.length > Math.ceil(max * 4 / 3) || !/^[A-Za-z0-9_-]+$/.test(value)) throw authFailure();
  const bytes = Buffer.from(value, 'base64url');
  if (bytes.length < size || bytes.length > max || b64(bytes) !== value) throw authFailure();
  return bytes;
}
function password(value, minimum = 1) {
  if (typeof value !== 'string' || value.length < minimum || value.length > 4096 || value.includes('\0')) throw fail(minimum === 12 ? 'Use a password of at least 12 characters and matching confirmation.' : 'Invalid password.');
}
function idValid(value) {
  if (typeof value !== 'string' || value.length > 128 || value.includes('\0')) throw fail('Invalid entry id.');
}
function revisionValid(value) {
  if (value !== undefined && (!Number.isSafeInteger(value) || value < 1)) throw fail('Invalid expected revision.');
}
// Reject getters, toJSON, class instances, cycles, sparse arrays and non-JSON values.
// Capture before queue admission: callers cannot change a pending write's meaning.
function snapshot(value) {
  let nodes = 0;
  const seen = new Set();
  function copy(item, depth) {
    if (++nodes > 100000 || depth > 32) throw fail('Invalid or oversized JSON value.');
    if (item === null || typeof item === 'boolean' || typeof item === 'string') return item;
    if (typeof item === 'number' && Number.isFinite(item)) return item;
    if ((!plain(item) && !Array.isArray(item)) || seen.has(item)) throw fail('Invalid JSON value.');
    seen.add(item);
    const result = Array.isArray(item) ? [] : {};
    const keys = Reflect.ownKeys(item);
    if (Array.isArray(item) && (keys.length !== item.length + 1 || keys.some(k => k !== 'length' && !/^(0|[1-9][0-9]*)$/.test(k)))) throw fail('Invalid JSON array.');
    for (const key of keys) {
      if (Array.isArray(item) && key === 'length') continue;
      const descriptor = Object.getOwnPropertyDescriptor(item, key);
      if (typeof key !== 'string' || !descriptor.enumerable || !('value' in descriptor)) throw fail('Invalid JSON property.');
      Object.defineProperty(result, key, { value: copy(descriptor.value, depth + 1), enumerable: true, writable: true, configurable: true });
    }
    seen.delete(item);
    return result;
  }
  return copy(value, 0);
}
function metadata(value) {
  if (!plain(value)) throw fail('Invalid metadata.');
  for (const [key, item] of Object.entries(value)) {
    if (strings.has(key)) {
      if (typeof item !== 'string' || item.length > (['notes', 'description'].includes(key) ? 8192 : 2048) || item.includes('\0')) throw fail('Invalid metadata field.');
    } else if (key === 'allowAgentUse') {
      if (typeof item !== 'boolean') throw fail('Invalid agent-use permission.');
    } else if (key === 'port') {
      if (!Number.isInteger(item) || item < 1 || item > 65535) throw fail('Invalid port.');
    } else if (key === 'tags') {
      if (!Array.isArray(item) || item.length > 100 || item.some(tag => typeof tag !== 'string' || tag.length > 128 || tag.includes('\0'))) throw fail('Invalid tags.');
    } else throw fail('Unsupported metadata fields.');
  }
  if (Buffer.byteLength(JSON.stringify(value)) > 32768) throw fail('Metadata is too large.');
  return value;
}
function secret(value) {
  if (typeof value !== 'string' && !plain(value)) throw fail('Invalid secret.');
  if (Buffer.byteLength(JSON.stringify(value)) > 1048576) throw fail('Secret is too large.');
  return value;
}
function header(document) {
  return Buffer.from(JSON.stringify({ version: document.version, id: document.id, kdf: KDF, salt: document.salt }));
}
function validateDocument(document) {
  if (!exact(document, ['version', 'id', 'kdf', 'salt', 'nonce', 'ciphertext', 'tag']) || document.version !== 2 || !exact(document.kdf, Object.keys(KDF)) || Object.keys(KDF).some(key => document.kdf[key] !== KDF[key])) throw authFailure();
  unb64(document.id, 16); unb64(document.salt, 16); unb64(document.nonce, 12); unb64(document.tag, 16);
  return document;
}
function validateRecords(payload) {
  if (!exact(payload, ['version', 'records']) || payload.version !== 1 || !Array.isArray(payload.records) || payload.records.length > MAX_RECORDS) throw authFailure();
  const ids = new Set();
  for (const row of payload.records) {
    if (!exact(row, ['id', 'metadata', 'secret', 'created', 'updated', 'revision'])) throw authFailure();
    idValid(row.id); metadata(row.metadata); secret(snapshot(row.secret)); revisionValid(row.revision);
    if (row.revision === undefined || ids.has(row.id) || ![row.created, row.updated].every(v => typeof v === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(v) && Number.isFinite(Date.parse(v)))) throw authFailure();
    ids.add(row.id);
  }
  return payload.records;
}
function safeStat(stat, directory = false) {
  if (stat.isSymbolicLink() || !(directory ? stat.isDirectory() : stat.isFile()) || (process.platform !== 'win32' && ((stat.mode & 0o077) || (typeof process.getuid === 'function' && stat.uid !== process.getuid())))) throw fail('Unsafe vault path or permissions.', 'UNSAFE_VAULT_PATH');
  if (!directory && stat.nlink !== 1) throw fail('Unsafe vault hard link.', 'UNSAFE_VAULT_PATH');
}

/** Pure Node storage. Internal-only: never expose internalGet to agents or RPC. */
export class VaultStore {
  #fs; #path; #directory; #owner; #gate; #serial = Promise.resolve(); #disposing = false; #disposal;
  #key; #document; #records; #fingerprint; #directoryIdentity; #failed = false;
  // The second argument is an internal, trusted filesystem fault-injection seam.
  constructor({ databasePath }, { filesystem = fs } = {}) {
    if (typeof databasePath !== 'string' || !databasePath || databasePath.includes('\0')) throw fail('Invalid vault path.');
    this.#path = path.resolve(databasePath); this.#fs = filesystem;
  }
  #enqueue(run, capture) {
    if (this.#disposing) return Promise.reject(fail('Vault is unavailable.', 'VAULT_DISPOSED'));
    let input;
    try { input = capture?.(); } catch (error) { return Promise.reject(error); }
    const result = this.#serial.then(async () => {
      if (this.#failed) throw fail('Vault is unavailable after an uncertain commit; dispose and reopen.', 'VAULT_UNCERTAIN_COMMIT');
      await this.#initialize();
      try { await this.#checkDirectory(); }
      catch (error) { this.#wipe(); this.#failed = true; throw error; }
      return run(input);
    });
    this.#serial = result.then(() => undefined, () => undefined);
    return result;
  }
  #ownerState(pid) {
    if (!Number.isSafeInteger(pid) || pid < 1) return 'INVALID';
    try { process.kill(pid, 0); return 'LIVE'; }
    catch (error) { return error.code === 'ESRCH' ? 'DEAD' : 'UNVERIFIED'; }
  }
  async #syncDirectory(directory) {
    if (process.platform === 'win32') return;
    const handle = await this.#fs.open(directory, 'r');
    try { await handle.sync(); } finally { await handle.close(); }
  }
  async #acquireGate(token) {
    const gatePath = `${this.#path}.node-owner`;
    const filename = `${process.pid}-${token}.json`;
    const temporary = `${gatePath}.prepare-${token}`;
    let prepared = false;
    try {
      await this.#fs.mkdir(temporary, { mode: 0o700 }); prepared = true;
      const handle = await this.#fs.open(path.join(temporary, filename), 'wx', 0o600);
      try { await handle.writeFile(JSON.stringify({ pid: process.pid, token })); await handle.sync(); } finally { await handle.close(); }
      await this.#syncDirectory(temporary);
      const preparedStat = await this.#fs.lstat(temporary); safeStat(preparedStat, true);
      // Publish only a populated directory. rename cannot replace another populated owner.
      for (let attempt = 0; attempt < 8; attempt++) {
        try {
          await this.#fs.rename(temporary, gatePath); prepared = false;
          this.#gate = { gatePath, filename, token, dev: preparedStat.dev, ino: preparedStat.ino };
          await this.#syncDirectory(this.#directory);
          return;
        } catch (error) {
          if (this.#gate) throw error;
          if (!['EEXIST', 'ENOTEMPTY', 'EPERM', 'EACCES'].includes(error.code)) throw error;
        }
        let names;
        try {
          const stat = await this.#fs.lstat(gatePath); safeStat(stat, true);
          names = await this.#fs.readdir(gatePath);
          if (names.length === 0) {
            // Only modern gates are atomically published nonempty. Empty means interrupted release.
            await this.#fs.rmdir(gatePath); continue;
          }
          if (names.length !== 1 || !/^[1-9][0-9]*-[a-f0-9]{64}\.json$/.test(names[0])) throw fail('Ambiguous Vault owner.', 'VAULT_BUSY', 'MODERN_INVALID');
          let observed;
          try { observed = JSON.parse(decoder.decode(await this.#readBounded(path.join(gatePath, names[0]), 1024))); }
          catch (error) { if (error.code === 'ENOENT') throw error; throw fail('Unverified Vault owner.', 'VAULT_BUSY', 'MODERN_INVALID'); }
          if (!exact(observed, ['pid', 'token']) || names[0] !== `${observed.pid}-${observed.token}.json`) throw fail('Ambiguous Vault owner.', 'VAULT_BUSY', 'MODERN_INVALID');
          const state = this.#ownerState(observed.pid);
          if (state !== 'DEAD') throw fail('Vault is owned by a live or unverified Host.', 'VAULT_BUSY', `MODERN_${state}`);
          // The immutable token filename prevents a delayed reclaimer deleting a successor.
          await this.#fs.unlink(path.join(gatePath, names[0]));
          await this.#fs.rmdir(gatePath);
        } catch (error) {
          if (['ENOENT', 'ENOTEMPTY', 'EEXIST'].includes(error.code)) continue;
          throw error;
        }
      }
      throw fail('Vault ownership is changing; retry.', 'VAULT_BUSY');
    } finally {
      if (prepared) {
        // This random path was created by this call, never a discovered/computed foreign target.
        await this.#fs.unlink(path.join(temporary, filename)).catch(error => { if (error.code !== 'ENOENT') throw error; });
        await this.#fs.rmdir(temporary);
      }
    }
  }
  async #checkGate() {
    const gate = this.#gate;
    if (!gate) throw fail('Vault ownership lost.', 'VAULT_OWNERSHIP_LOST');
    const stat = await this.#fs.lstat(gate.gatePath); safeStat(stat, true);
    if (stat.dev !== gate.dev || stat.ino !== gate.ino) throw fail('Vault ownership changed.', 'VAULT_OWNERSHIP_LOST');
    const value = JSON.parse(decoder.decode(await this.#readBounded(path.join(gate.gatePath, gate.filename), 1024)));
    if (!exact(value, ['pid', 'token']) || value.pid !== process.pid || value.token !== gate.token) throw fail('Vault ownership changed.', 'VAULT_OWNERSHIP_LOST');
  }
  async #releaseGate() {
    if (!this.#gate) return;
    await this.#checkGate();
    const gate = this.#gate;
    await this.#fs.unlink(path.join(gate.gatePath, gate.filename));
    this.#gate = undefined; // No populated gate remains ours, even if empty-dir cleanup fails.
    await this.#fs.rmdir(gate.gatePath).catch(() => {});
  }
  async #publishLegacy(lockPath, token) {
    const temporary = `${lockPath}.prepare-${token}`;
    const ownerPath = path.join(temporary, 'owner.json');
    let prepared = false;
    try {
      await this.#fs.mkdir(temporary, { mode: 0o700 }); prepared = true;
      const handle = await this.#fs.open(ownerPath, 'wx', 0o600);
      try { await handle.writeFile(JSON.stringify({ pid: process.pid, token })); await handle.sync(); } finally { await handle.close(); }
      await this.#syncDirectory(temporary);
      const stat = await this.#fs.lstat(temporary); safeStat(stat, true);
      // Retain the v2.0.x gate, but never expose an incomplete legacy owner ourselves.
      await this.#fs.rename(temporary, lockPath); prepared = false;
      this.#owner = { token, lockPath, ownerPath: path.join(lockPath, 'owner.json'), dev: stat.dev, ino: stat.ino };
    } finally {
      if (prepared) {
        await this.#fs.unlink(ownerPath).catch(error => { if (error.code !== 'ENOENT') throw error; });
        await this.#fs.rmdir(temporary);
      }
    }
  }
  async #retireLegacy(lockPath, token) {
    // Atomically unpublish before cleanup; a crash cannot leave an empty legacy gate.
    const retired = `${lockPath}.retired-${token}`;
    await this.#fs.rename(lockPath, retired);
    // Retirement is complete once unpublished. Metadata-only garbage cleanup must
    // not strand the still-live PID's modern gate after an otherwise safe release.
    await this.#fs.unlink(path.join(retired, 'owner.json')).then(() => this.#fs.rmdir(retired)).catch(() => {});
  }
  async #initialize() {
    if (this.#owner) return;
    const directory = path.dirname(this.#path);
    await this.#fs.mkdir(directory, { recursive: true, mode: 0o700 });
    const directoryStat = await this.#fs.lstat(directory); safeStat(directoryStat, true);
    const canonical = await this.#fs.realpath(directory);
    this.#path = path.join(canonical, path.basename(this.#path)); this.#directory = canonical;
    this.#directoryIdentity = { dev: directoryStat.dev, ino: directoryStat.ino };
    if (owners.has(this.#path)) throw fail('Vault is owned by another store. Dispose its owner first.', 'VAULT_BUSY', 'IN_PROCESS');
    const token = randomBytes(32).toString('hex');
    owners.set(this.#path, token);
    const lockPath = `${this.#path}.node-lock`;
    let made = false;
    try {
      await this.#acquireGate(token);
      try { await this.#publishLegacy(lockPath, token); made = true; }
      catch (error) {
        if (!['EEXIST', 'ENOTEMPTY', 'EPERM', 'EACCES'].includes(error.code)) throw error;
        const legacyStat = await this.#fs.lstat(lockPath); safeStat(legacyStat, true);
        let legacy;
        try { legacy = JSON.parse(decoder.decode(await this.#readBounded(path.join(lockPath, 'owner.json'), 1024))); }
        catch { throw fail('Vault has an incomplete or unverified legacy owner.', 'VAULT_BUSY', 'LEGACY_INVALID'); }
        if (!exact(legacy, ['pid', 'token']) || !/^[a-f0-9]{64}$/.test(legacy.token)) throw fail('Vault has an unverified legacy owner.', 'VAULT_BUSY', 'LEGACY_INVALID');
        const state = this.#ownerState(legacy.pid);
        if (state !== 'DEAD') throw fail('Vault is owned by a live or unverified Host.', 'VAULT_BUSY', `LEGACY_${state}`);
        // Modern gate serializes fixed-filename legacy recovery. A v2.0.x owner cannot
        // acquire the populated legacy lock; if it wins the following mkdir, abort.
        await this.#checkGate();
        await this.#retireLegacy(lockPath, token);
        try { await this.#publishLegacy(lockPath, token); made = true; }
        catch (error) { if (['EEXIST', 'ENOTEMPTY', 'EPERM', 'EACCES'].includes(error.code)) throw fail('Another Host acquired Vault ownership.', 'VAULT_BUSY'); throw error; }
      }
      await this.#checkDirectory();
      await this.#syncDirectory(this.#directory);
    } catch (error) {
      if (this.#owner) {
        try {
          await this.#checkDirectory(); await this.#retireLegacy(lockPath, token);
          this.#owner = undefined;
        } catch { this.#failed = true; } // Preserve both gates for safe disposal retry.
      } else if (made) {
        // Published but could not verify its identity. Never guess ownership.
        this.#failed = true;
      }
      if (!this.#owner) {
        await this.#releaseGate().catch(() => { this.#failed = true; });
        if (!this.#gate && owners.get(this.#path) === token) owners.delete(this.#path);
      }
      throw error;
    }
  }
  async #checkDirectory() {
    await this.#checkGate();
    const directoryStat = await this.#fs.lstat(this.#directory); safeStat(directoryStat, true);
    if (directoryStat.dev !== this.#directoryIdentity.dev || directoryStat.ino !== this.#directoryIdentity.ino) throw fail('Vault directory changed.', 'UNSAFE_VAULT_PATH');
    if (await this.#fs.realpath(this.#directory) !== this.#directory) throw fail('Unsafe vault directory.', 'UNSAFE_VAULT_PATH');
    const owner = this.#owner;
    const stat = await this.#fs.lstat(owner.lockPath); safeStat(stat, true);
    if (stat.dev !== owner.dev || stat.ino !== owner.ino) throw fail('Vault ownership changed.', 'VAULT_OWNERSHIP_LOST');
    const ownerFile = await this.#readBounded(owner.ownerPath, 1024);
    const recorded = JSON.parse(decoder.decode(ownerFile));
    if (!exact(recorded, ['pid', 'token']) || recorded.pid !== process.pid || recorded.token !== owner.token) throw fail('Vault ownership changed.', 'VAULT_OWNERSHIP_LOST');
  }
  async #readBounded(file, maximum) {
    const before = await this.#fs.lstat(file); safeStat(before);
    if (before.size > maximum) throw fail('Vault file is too large.', 'VAULT_TOO_LARGE');
    const handle = await this.#fs.open(file, constants.O_RDONLY | (constants.O_NOFOLLOW || 0));
    try {
      const stat = await handle.stat(); safeStat(stat);
      if (stat.ino !== before.ino || stat.dev !== before.dev || stat.size > maximum) throw fail('Vault file changed or is too large.');
      const buffer = Buffer.alloc(stat.size + 1);
      let count = 0;
      while (count < buffer.length) {
        const { bytesRead } = await handle.read(buffer, count, buffer.length - count, null);
        if (!bytesRead) break;
        count += bytesRead;
      }
      if (count !== stat.size) throw fail('Vault file changed while reading.');
      return buffer.subarray(0, count);
    } finally { await handle.close(); }
  }
  async #exists() {
    await this.#checkDirectory();
    try { safeStat(await this.#fs.lstat(this.#path)); return true; }
    catch (error) { if (error.code === 'ENOENT') return false; throw error; }
  }
  #require() { if (!this.#key) throw fail('Vault is locked.', 'VAULT_LOCKED'); }
  #wipe() { this.#key?.fill(0); this.#key = undefined; this.#document = undefined; this.#records = undefined; this.#fingerprint = undefined; }
  async #status() { return { exists: await this.#exists(), unlocked: !!this.#key }; }
  status() { return this.#enqueue(() => this.#status()); }
  setup(value, confirmation) {
    return this.#enqueue(async () => {
      password(value, 12);
      if (value !== confirmation) throw fail('Use a password of at least 12 characters and matching confirmation.');
      if (await this.#exists()) throw fail('Vault already exists.');
      const document = { version: 2, id: b64(randomBytes(16)), kdf: KDF, salt: b64(randomBytes(16)) };
      const key = await derive(value, unb64(document.salt, 16), 32, KDF);
      try { await this.#commit([], document, key); } finally { if (this.#key !== key) key.fill(0); }
      return this.#status();
    });
  }
  unlock(value) {
    return this.#enqueue(async () => {
      password(value);
      if (this.#key) throw fail('Lock the vault first.');
      if (!(await this.#exists())) throw fail('Vault is not initialized.');
      const bytes = await this.#readBounded(this.#path, MAX_FILE_BYTES);
      if (!bytes.subarray(0, MAGIC.length).equals(Buffer.from(MAGIC))) throw fail('Legacy SQLCipher or unknown vault format. Preserve the file and use the previous compatible plugin; no automatic migration is supported.', 'LEGACY_VAULT_FORMAT');
      let key, plaintext;
      try {
        const document = validateDocument(JSON.parse(decoder.decode(bytes.subarray(MAGIC.length))));
        const ciphertext = unb64(document.ciphertext, 1, MAX_FILE_BYTES);
        key = await derive(value, unb64(document.salt, 16), 32, KDF);
        const decipher = createDecipheriv('aes-256-gcm', key, unb64(document.nonce, 12));
        decipher.setAAD(header(document)); decipher.setAuthTag(unb64(document.tag, 16));
        const chunk = decipher.update(ciphertext);
        try { plaintext = Buffer.concat([chunk, decipher.final()]); } finally { chunk.fill(0); }
        const records = validateRecords(JSON.parse(decoder.decode(plaintext)));
        this.#document = document; this.#records = records; this.#key = key;
        this.#fingerprint = createHash('sha256').update(bytes).digest('hex'); key = undefined;
      } catch { throw authFailure(); }
      finally { key?.fill(0); plaintext?.fill(0); }
      return this.#status();
    });
  }
  lock() { return this.#enqueue(async () => { this.#wipe(); return this.#status(); }); }
  rekey(value) {
    return this.#enqueue(async () => {
      this.#require(); password(value, 12);
      const document = { ...this.#document, salt: b64(randomBytes(16)) };
      const key = await derive(value, unb64(document.salt, 16), 32, KDF);
      try { await this.#commit(this.#records, document, key); } finally { if (this.#key !== key) key.fill(0); }
      return this.#status();
    });
  }
  list() {
    return this.#enqueue(() => {
      this.#require();
      return this.#records.map(({ secret: omitted, ...row }) => snapshot(row)).sort((a, b) => b.updated.localeCompare(a.updated) || a.id.localeCompare(b.id));
    });
  }
  // Internal UI list remains complete; model discovery clones only its page.
  listPage(options = {}) {
    return this.#enqueue(({offset=0,limit=100,query=''}) => {
      this.#require();
      if (!Number.isSafeInteger(offset) || offset < 0 || offset > MAX_RECORDS || !Number.isSafeInteger(limit) || limit < 1 || limit > 100 || typeof query !== 'string' || query.length > 256) throw fail('Use offset 0–4096, limit 1–100 and query up to 256 characters.', 'VAULT_INVALID_ARGUMENTS');
      const needle=query.toLowerCase();
      const rows=this.#records.filter(row=>!needle || [row.id,...Object.entries(row.metadata).filter(([key])=>key!=='allowAgentUse').flatMap(([,value])=>Array.isArray(value)?value:[value])].join(' ').toLowerCase().includes(needle)).sort((a,b)=>b.updated.localeCompare(a.updated)||a.id.localeCompare(b.id));
      return {records:rows.slice(offset,offset+limit).map(({secret:omitted,...row})=>snapshot(row)),total:rows.length,nextOffset:offset+limit<rows.length?offset+limit:null};
    },()=>snapshot(options));
  }
  getMetadata(id) {
    return this.#enqueue(()=>{
      const row=this.#row(id,undefined,true);
      if(!row)return undefined;
      const {secret:omitted,...result}=row;return snapshot(result);
    });
  }
  #row(id, expectedRevision, missingOkay = false) {
    this.#require(); idValid(id); revisionValid(expectedRevision);
    const row = this.#records.find(item => item.id === id);
    if (expectedRevision !== undefined && row?.revision !== expectedRevision) throw fail('Entry revision conflict. Reload the entry and retry.', 'VAULT_CONFLICT');
    if (!row && !missingOkay) throw fail('Entry not found.', 'VAULT_NOT_FOUND');
    return row;
  }
  save(data) {
    return this.#enqueue(async input => {
      this.#require();
      if (!plain(input) || Object.keys(input).some(k => !['metadata', 'secret', 'id', 'expectedRevision'].includes(k))) throw fail('Invalid vault request.');
      metadata(input.metadata); secret(input.secret); revisionValid(input.expectedRevision);
      const creating = input.id == null;
      if (creating && input.expectedRevision !== undefined) throw fail('A new entry cannot have an expected revision.');
      const old = creating ? undefined : this.#row(input.id, input.expectedRevision);
      if (creating && this.#records.length >= MAX_RECORDS) throw fail('Vault record limit reached.', 'VAULT_RECORD_LIMIT');
      if (old?.revision === Number.MAX_SAFE_INTEGER) throw fail('Entry revision limit reached.');
      const now = new Date().toISOString();
      const row = { id: old?.id ?? randomUUID(), metadata: input.metadata, secret: input.secret, created: old?.created ?? now, updated: now, revision: (old?.revision ?? 0) + 1 };
      const records = old ? this.#records.map(item => item === old ? row : item) : [...this.#records, row];
      await this.#commit(records); return { id: row.id };
    }, () => {
      if (!plain(data)) throw fail('Invalid vault request.');
      const captured = {};
      for (const key of Reflect.ownKeys(data)) {
        const descriptor = Object.getOwnPropertyDescriptor(data, key);
        if (typeof key !== 'string' || !descriptor.enumerable || !('value' in descriptor)) throw fail('Invalid vault request.');
        if (descriptor.value === undefined && ['id', 'expectedRevision'].includes(key)) continue;
        Object.defineProperty(captured, key, { value: snapshot(descriptor.value), enumerable: true, writable: true, configurable: true });
      }
      return captured;
    });
  }
  updateMetadata(id, value, expectedRevision) {
    return this.#enqueue(async captured => {
      const old = this.#row(id, expectedRevision); metadata(captured);
      if (old.revision === Number.MAX_SAFE_INTEGER) throw fail('Entry revision limit reached.');
      const row = { ...old, metadata: captured, updated: new Date().toISOString(), revision: old.revision + 1 };
      await this.#commit(this.#records.map(item => item === old ? row : item)); return { id };
    }, () => snapshot(value));
  }
  delete(id, expectedRevision) {
    return this.#enqueue(async () => {
      const row = this.#row(id, expectedRevision, true);
      if (row) await this.#commit(this.#records.filter(item => item !== row));
      return { deleted: true };
    });
  }
  internalGet(id) { return this.#enqueue(() => snapshot(this.#row(id).secret)); }
  async #commit(records, document = this.#document, key = this.#key) {
    await this.#checkDirectory();
    await this.#exists(); // Reject symlink/unsafe targets immediately before writing.
    let plaintext;
    try {
      plaintext = Buffer.from(JSON.stringify({ version: 1, records }));
      if (plaintext.length > MAX_FILE_BYTES) throw fail('Vault file is too large.', 'VAULT_TOO_LARGE');
      const nonce = randomBytes(12);
      const cipher = createCipheriv('aes-256-gcm', key, nonce); cipher.setAAD(header(document));
      const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
      const next = { version: document.version, id: document.id, kdf: KDF, salt: document.salt, nonce: b64(nonce), ciphertext: b64(ciphertext), tag: b64(cipher.getAuthTag()) };
      const encoded = Buffer.from(MAGIC + JSON.stringify(next));
      if (encoded.length > MAX_FILE_BYTES) throw fail('Vault file is too large.', 'VAULT_TOO_LARGE');
      await this.#atomicWrite(encoded);
      if (this.#key !== key) this.#key?.fill(0);
      this.#key = key; this.#document = next; this.#records = records;
      this.#fingerprint = createHash('sha256').update(encoded).digest('hex');
    } finally { plaintext?.fill(0); }
  }
  async #assertTargetUnchanged() {
    const exists = await this.#exists();
    if (this.#fingerprint === undefined) {
      if (exists) throw fail('Vault already exists.');
      return;
    }
    const actual = exists ? createHash('sha256').update(await this.#readBounded(this.#path, MAX_FILE_BYTES)).digest('hex') : undefined;
    if (actual !== this.#fingerprint) {
      this.#wipe(); this.#failed = true;
      throw fail('Vault file changed outside its owner. Dispose and reopen.', 'VAULT_EXTERNAL_CHANGE');
    }
  }
  async #atomicWrite(bytes) {
    const temporary = path.join(this.#directory, `.vault-${randomBytes(16).toString('hex')}.tmp`);
    let handle, created = false, renameAttempted = false;
    try {
      handle = await this.#fs.open(temporary, 'wx', 0o600); created = true;
      await handle.writeFile(bytes); await handle.sync(); await handle.close(); handle = undefined;
      await this.#checkDirectory();
      await this.#assertTargetUnchanged();
      renameAttempted = true;
      await this.#fs.rename(temporary, this.#path);
      // Windows cannot reliably open/fsync directories; see README for durability limit.
      if (process.platform !== 'win32') {
        const directory = await this.#fs.open(this.#directory, 'r');
        try { await directory.sync(); } finally { await directory.close(); }
      }
    } catch (error) {
      if (renameAttempted) { this.#wipe(); this.#failed = true; throw fail('Vault commit outcome is uncertain. Dispose and reopen before continuing.', 'VAULT_UNCERTAIN_COMMIT'); }
      throw error;
    } finally {
      if (handle) await handle.close().catch(() => {});
      if (created) await this.#fs.unlink(temporary).catch(error => {
        if (error.code === 'ENOENT') return;
        if (renameAttempted) {
          this.#wipe(); this.#failed = true;
          throw fail('Vault commit cleanup outcome is uncertain. Dispose and reopen.', 'VAULT_UNCERTAIN_COMMIT');
        }
        throw error;
      });
    }
  }
  dispose() {
    if (this.#disposal) return this.#disposal;
    this.#disposing = true;
    this.#disposal = this.#serial.then(async () => {
      this.#wipe();
      const owner = this.#owner;
      const token = owner?.token ?? this.#gate?.token;
      if (owner) {
        await this.#checkDirectory(); // Never remove a lock whose ownership changed.
        await this.#retireLegacy(owner.lockPath, owner.token);
        this.#owner = undefined;
      }
      await this.#releaseGate();
      if (token && owners.get(this.#path) === token) owners.delete(this.#path);
    }).catch(error => {
      // Still reject new work, but allow explicit disposal retry after transient I/O.
      this.#disposal = undefined;
      throw error;
    });
    return this.#disposal;
  }
}
