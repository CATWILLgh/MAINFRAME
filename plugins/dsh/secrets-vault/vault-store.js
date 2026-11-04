import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

/** Internal-only bridge. Never expose internalGet through RPC/tools/client services. */
export class VaultStore {
  constructor({ python, databasePath, workerPath = fileURLToPath(new URL('./vault.py', import.meta.url)) }) {
    this.python = python;
    this.databasePath = databasePath;
    this.workerPath = workerPath;
    this.child = null;
    this.pending = new Map();
    this.serial = Promise.resolve();
    this.counter = 0;
    this.disposed = false;
  }
  start() {
    if (this.disposed) throw new Error('Vault is unavailable.');
    if (this.child) return;
    // No credentials in argv/env; stderr intentionally discarded (SQLCipher may log).
    const child = spawn(this.python, ['-u', this.workerPath, this.databasePath], {
      stdio: ['pipe', 'pipe', 'ignore'], windowsHide: true,
      env: { PATH: process.env.PATH || '/usr/bin:/bin', HOME: process.env.HOME || '', LANG: 'en_US.UTF-8', PYTHONNOUSERSITE: '1' },
    });
    this.child = child;
    const lines = createInterface({ input: child.stdout });
    const fail = () => {
      if (this.child !== child) return;
      this.child = null;
      for (const { reject, timer } of this.pending.values()) { clearTimeout(timer); reject(new Error('Vault worker is unavailable.')); }
      this.pending.clear();
      lines.close();
    };
    child.once('error', fail);
    child.once('exit', fail);
    child.stdin.on('error', () => {});
    lines.on('line', (line) => {
      let message;
      try { message = JSON.parse(line); } catch { child.kill(); return; }
      const item = this.pending.get(message.id);
      if (!item) return;
      this.pending.delete(message.id);
      clearTimeout(item.timer);
      if (typeof message.error === 'string') item.reject(new Error(message.error));
      else item.resolve(message.result);
    });
  }
  request(method, params = {}) {
    const run = () => new Promise((resolve, reject) => {
      try { this.start(); } catch { reject(new Error('Vault is unavailable.')); return; }
      const id = ++this.counter;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        this.child?.kill();
        reject(new Error('Vault operation timed out.'));
      }, 30000);
      this.pending.set(id, { resolve, reject, timer });
      let encoded;
      try { encoded = JSON.stringify({ id, method, params }) + '\n'; }
      catch { clearTimeout(timer); this.pending.delete(id); reject(new Error('Invalid vault request.')); return; }
      this.child.stdin.write(encoded, (error) => {
        if (!error) return;
        clearTimeout(timer); this.pending.delete(id); reject(new Error('Vault worker is unavailable.'));
      });
    });
    const result = this.serial.then(run, run);
    this.serial = result.then(() => undefined, () => undefined);
    return result;
  }
  status() { return this.request('status'); }
  list() { return this.request('list'); }
  setup(password, confirmation) { return this.request('setup', { password, confirmation }); }
  unlock(password) { return this.request('unlock', { password }); }
  lock() { return this.request('lock'); }
  rekey(password) { return this.request('rekey', { password }); }
  save(data) { return this.request('save', data); }
  delete(id) { return this.request('delete', { id }); }
  updateMetadata(id, metadata) { return this.request('updateMetadata', { id, metadata }); }
  internalGet(id) { return this.request('internalGet', { id }); }
  async dispose() {
    try { if (this.child) await this.lock(); } finally {
      this.disposed = true;
      const child=this.child;
      if(child)await new Promise(resolve=>{child.once('exit',resolve);child.kill();});
    }
  }
}
