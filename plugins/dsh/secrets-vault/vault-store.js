import path from 'node:path';
import { lstat } from 'node:fs/promises';
import { VaultStore as NodeVaultStore } from './core/index.js';

/** DSH adapter only. Never expose internalGet through RPC/tools/client services. */
export class VaultStore {
  constructor({ databasePath, python, workerPath, ...options }) {
    if (python !== undefined || workerPath !== undefined) throw new Error('Python Vault options are no longer supported. Remove the obsolete override.');
    this.databasePath = path.resolve(databasePath);
    this.core = new NodeVaultStore({ databasePath: this.databasePath, ...options });
    this.disposed = false;
    this.serial = Promise.resolve();
  }
  _call(method, ...args) {
    if (this.disposed) return Promise.reject(new Error('Vault is unavailable.'));
    const result = this.serial.then(() => this._run(method, args));
    this.serial = result.catch(() => {});
    return result;
  }
  async _run(method, args) {
    // The formats must never share a path or silently initialize over old data.
    // Inspect existence only: the legacy database and envelopes remain untouched.
    if (path.basename(this.databasePath) === 'vault.v2.json') {
      for (const name of ['vault.db', 'vault.db.recovery.json']) {
        try { await lstat(path.join(path.dirname(this.databasePath), name)); }
        catch (error) { if (error.code === 'ENOENT') continue; throw error; }
        throw Object.assign(new Error('A legacy Vault was found. Preserve its files and use the previous plugin to access it. Automatic SQLCipher migration is not supported.'), { code: 'LEGACY_VAULT_FORMAT' });
      }
    }
    return this.core[method](...args);
  }
  status() { return this._call('status'); }
  list() { return this._call('list'); }
  listPage(options) { return this._call('listPage', structuredClone(options)); }
  getMetadata(id) { return this._call('getMetadata', id); }
  setup(password, confirmation) { return this._call('setup', password, confirmation); }
  unlock(password) { return this._call('unlock', password); }
  lock() { return this._call('lock'); }
  rekey(password) { return this._call('rekey', password); }
  save(data) { return this._call('save', structuredClone(data)); }
  delete(id, expectedRevision) { return this._call('delete', id, expectedRevision); }
  updateMetadata(id, metadata, expectedRevision) { return this._call('updateMetadata', id, structuredClone(metadata), expectedRevision); }
  internalGet(id) { return this._call('internalGet', id); }
  dispose() {
    if (!this.disposal) {
      this.disposed = true;
      this.disposal = this.serial.then(() => this.core.dispose()).catch(error => {
        this.disposal = undefined; // Retry a transient release failure without reopening admission.
        throw error;
      });
    }
    return this.disposal;
  }
}
