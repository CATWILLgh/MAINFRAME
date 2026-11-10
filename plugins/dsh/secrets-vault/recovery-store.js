import { randomBytes, scrypt, createCipheriv, createDecipheriv } from 'node:crypto';
import { promisify } from 'node:util';
const deriveKey = promisify(scrypt);
import { promises as fs, constants } from 'node:fs';
import path from 'node:path';

// Internal host helper: none of its key-returning methods belong in agent tools.
// Back up vault.v2.json AND its .recovery.json envelope together while locked.
const VERSION = 1;
const PREFIX = 'dsh-recovery-v1-';
const KDF = { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };
const failure = () => new Error('Vault authentication or recovery failed. Preserve the vault and recovery files.');
const b64 = value => Buffer.from(value).toString('base64url');
function decode(value, size) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value)) throw failure();
  const bytes = Buffer.from(value, 'base64url');
  if (bytes.length !== size || b64(bytes) !== value) throw failure();
  return bytes;
}
function passwordValid(password, confirmation) {
  if (typeof password !== 'string' || password.length < 12 || password.length > 4096 || password.includes('\0') || password !== confirmation) throw new Error('Use a password of at least 12 characters and matching confirmation.');
}
function aad(document, kind) { return Buffer.from(`dsh-vault-recovery:${VERSION}:${document.id}:${document.generation}:${kind}`); }
function seal(key, plaintext, associated) {
  const nonce = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, nonce);
  cipher.setAAD(associated);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  return { nonce: b64(nonce), ciphertext: b64(ciphertext), tag: b64(cipher.getAuthTag()) };
}
function open(key, envelope, associated) {
  if (!envelope || typeof envelope.ciphertext !== 'string' || envelope.ciphertext.length > 16000) throw failure();
  const ciphertext = Buffer.from(envelope.ciphertext, 'base64url');
  if (!ciphertext.length || b64(ciphertext) !== envelope.ciphertext) throw failure();
  const cipher = createDecipheriv('aes-256-gcm', key, decode(envelope.nonce, 12));
  cipher.setAAD(associated);
  cipher.setAuthTag(decode(envelope.tag, 16));
  const chunk = cipher.update(ciphertext);
  let tail;
  try { tail = cipher.final(); return Buffer.concat([chunk, tail]); }
  finally { chunk.fill(0); tail?.fill(0); }
}
async function wrap(document, kind, credential, key) {
  const salt = randomBytes(16);
  const kek = await deriveKey(credential, salt, 32, KDF);
  let plaintext;
  try { plaintext = Buffer.from(key, 'utf8'); return { salt: b64(salt), ...seal(kek, plaintext, aad(document, kind)) }; }
  finally { kek.fill(0); plaintext?.fill(0); }
}
async function unwrap(document, kind, credential) {
  const envelope = document[kind];
  const kek = await deriveKey(credential, decode(envelope?.salt, 16), 32, KDF);
  try {
    const plaintext = open(kek, envelope, aad(document, kind));
    try {
      const key = plaintext.toString('utf8');
      if (!/^[a-f0-9]{64}$/.test(key)) throw failure();
      return key;
    } finally { plaintext.fill(0); }
  } finally { kek.fill(0); }
}
function recoveryCredential(value) {
  if (typeof value !== 'string' || !value.startsWith(PREFIX)) throw failure();
  return decode(value.slice(PREFIX.length), 32);
}

export class RecoveryStore {
  constructor(store, databasePath) {
    this.store = store;
    this.databasePath = path.resolve(databasePath);
    this.sidecarPath = `${this.databasePath}.recovery.json`;
  }
  async _read() {
    let stat;
    try { stat = await fs.lstat(this.sidecarPath); } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
    const safe = info => info.isFile() && !info.isSymbolicLink() && info.nlink === 1 && info.size <= 32768 && (process.platform === 'win32' || (!(info.mode & 0o077) && (typeof process.getuid !== 'function' || info.uid === process.getuid())));
    if (!safe(stat)) throw failure();
    const handle = await fs.open(this.sidecarPath, constants.O_RDONLY | (constants.O_NOFOLLOW || 0));
    let bytes;
    try {
      const opened = await handle.stat();
      if (!safe(opened) || opened.dev !== stat.dev || opened.ino !== stat.ino) throw failure();
      const buffer = Buffer.alloc(opened.size + 1); let count = 0;
      while (count < buffer.length) {
        const {bytesRead} = await handle.read(buffer, count, buffer.length-count, null);
        if (!bytesRead) break;
        count += bytesRead;
      }
      if (count !== opened.size) throw failure();
      bytes = buffer.subarray(0,count);
    } finally { await handle.close(); }
    const document = JSON.parse(bytes.toString('utf8'));
    if (document.version !== VERSION || !Number.isSafeInteger(document.generation) || document.generation < 1) throw failure();
    decode(document.id, 16);
    if (!document.password || !document.recovery) throw failure();
    return document;
  }
  async _write(document, exclusive = false) {
    const directory = path.dirname(this.sidecarPath);
    await fs.mkdir(directory, { recursive: true, mode: 0o700 });
    const directoryStat = await fs.lstat(directory);
    if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink() || (process.platform !== 'win32' && ((directoryStat.mode & 0o077) || (typeof process.getuid === 'function' && directoryStat.uid !== process.getuid())))) throw failure();
    const previous = await this._read();
    if (exclusive && previous) throw new Error('Recovery is already enabled.');
    const temporary = path.resolve(directory, `.recovery-${randomBytes(16).toString('hex')}.tmp`);
    if (path.dirname(temporary) !== directory || !/^\.recovery-[a-f0-9]{32}\.tmp$/.test(path.basename(temporary))) throw failure();
    let handle;
    try {
      handle = await fs.open(temporary, 'wx', 0o600);
      await handle.writeFile(JSON.stringify(document));
      await handle.sync();
      await handle.close(); handle = null;
      // Caller must serialize the whole operation, including database rekey.
      await fs.rename(temporary, this.sidecarPath);
      if (process.platform !== 'win32') {
        const dir = await fs.open(directory, 'r');
        try { await dir.sync(); } finally { await dir.close(); }
      }
    } finally {
      if (handle) await handle.close();
      // temporary is a fixed, locally generated path, never caller-controlled.
      try { await fs.unlink(temporary); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
  }
  async _new(password, previous, legacyKey) {
    const key = randomBytes(32).toString('hex');
    const credential = randomBytes(32);
    const recoveryKey = PREFIX + b64(credential);
    const document = { version: VERSION, id: previous?.id || b64(randomBytes(16)), generation: (previous?.generation || 0) + 1 };
    try {
      document.password = await wrap(document, 'password', password, key);
      document.recovery = await wrap(document, 'recovery', credential, key);
      // This common bridge is deletable after migration without either credential.
      if (legacyKey !== undefined) {
        const migrationKey = Buffer.from(key, 'hex');
        const plaintext = Buffer.from(JSON.stringify({ legacyKey }));
        try { document.migration = seal(migrationKey, plaintext, aad(document, 'migration')); }
        finally { migrationKey.fill(0); plaintext.fill(0); }
      }
      return { document, key, recoveryKey };
    } finally { credential.fill(0); }
  }
  async _open(document, key) {
    await this.store.lock();
    try { await this.store.unlock(key); }
    catch {
      if (!document.migration) throw failure();
      const migrationKey = Buffer.from(key, 'hex');
      let plaintext, legacyKey;
      try {
        plaintext = open(migrationKey, document.migration, aad(document, 'migration'));
        ({ legacyKey } = JSON.parse(plaintext.toString('utf8')));
      } finally { migrationKey.fill(0); plaintext?.fill(0); }
      if (typeof legacyKey !== 'string' || !legacyKey || legacyKey.length > 4096 || legacyKey.includes('\0')) throw failure();
      await this.store.unlock(legacyKey);
      await this.store.rekey(key);
      // Reopening verifies the committed database before deleting the bridge.
      await this.store.lock();
      await this.store.unlock(key);
    }
    if (document.migration) {
      const clean = { ...document }; delete clean.migration;
      await this._write(clean);
    }
    return this.store.status();
  }
  async status() {
    // The Node store acquires lifetime exclusive ownership before sidecar access.
    const status = await this.store.status();
    const document = await this._read();
    return { ...status, recoveryAvailable: !!document };
  }
  async setup(password, confirmation) {
    passwordValid(password, confirmation);
    if ((await this.store.status()).exists || await this._read()) throw new Error('Vault already exists or setup needs manual repair.');
    const { document, key, recoveryKey } = await this._new(password);
    // Persist first: never create a random-key DB whose key envelope is absent.
    await this._write(document, true);
    await this.store.setup(key, key);
    return { recoveryKey };
  }
  async unlock(password) {
    await this.store.status();
    const document = await this._read();
    if (!document) return this.store.unlock(password);
    if (typeof password !== 'string' || !password || password.length > 4096 || password.includes('\0')) throw failure();
    return this._open(document, await unwrap(document, 'password', password));
  }
  async enable(password) {
    await this.store.status();
    if (await this._read()) throw new Error('Recovery is already enabled.');
    if (typeof password !== 'string' || !password || password.length > 4096 || password.includes('\0')) throw failure();
    // An unlocked session is not fresh master-password authentication.
    await this.store.lock();
    await this.store.unlock(password);
    const { document, key, recoveryKey } = await this._new(password, null, password);
    await this._write(document, true);
    await this._open(document, key);
    return { recoveryKey };
  }
  async recover(recoveryKey, password, confirmation) {
    passwordValid(password, confirmation);
    await this.store.status();
    const document = await this._read();
    if (!document) throw failure();
    const credential = recoveryCredential(recoveryKey);
    let key;
    try { key = await unwrap(document, 'recovery', credential); } finally { credential.fill(0); }
    await this._open(document, key);
    return this._rotate(document, key, password);
  }
  async rotate(password) {
    await this.store.status();
    const document = await this._read();
    if (!document || typeof password !== 'string' || !password || password.length > 4096 || password.includes('\0')) throw failure();
    const key = await unwrap(document, 'password', password);
    await this._open(document, key);
    return this._rotate(document, key, password);
  }
  async _rotate(previous, oldKey, password) {
    const { document, key, recoveryKey } = await this._new(password, previous, oldKey);
    // New credentials become authoritative at this durable rename. Until rekey
    // finishes, the authenticated migration bridge opens only the previous DB.
    await this._write(document);
    await this._open(document, key);
    return { recoveryKey };
  }
  lock() { return this.store.lock(); }
}
