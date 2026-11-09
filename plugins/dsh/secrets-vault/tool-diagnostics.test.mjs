import test from 'node:test';
import {ownedEffects} from './test-effects.mjs';
import assert from 'node:assert/strict';
import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { apply } from './index.js';

// Temporary synthetic profiles only. Never inspect an installed profile or real credentials.
async function fixture(t) {
  const root = await fs.realpath(os.tmpdir());
  const profile = await fs.mkdtemp(path.join(root, 'vault-tool-diagnostics-synthetic-'));
  let tool;const {effect,on,dispose}=ownedEffects();
  const ctx = {
    effect,on,
    connection: { fetch: { register: () => () => {} } },
    tools: { register: value => { tool = value; return () => {}; } },
    systemPrompt: { section: () => () => {} },
    agents: { get: () => undefined },
  };
  apply(ctx, { profileDirectory: profile });
  t.after(async () => {
    try { await dispose(); }
    finally {
      assert.equal(path.dirname(path.resolve(profile)), root);
      assert.match(path.basename(profile), /^vault-tool-diagnostics-synthetic-/);
      await fs.rm(profile, { recursive: true });
    }
  });
  return { profile, tool, directory: path.join(profile, 'secrets-vault') };
}
function noRawDetails(result, values) {
  const encoded = JSON.stringify(result);
  for (const value of values) assert.equal(encoded.includes(String(value)), false, `Raw diagnostic leaked: ${value}`);
  assert.equal(encoded.includes('stack'), false);
}

test('tool reports live legacy ownership with static VAULT_BUSY and no owner details', async t => {
  const { profile, tool, directory } = await fixture(t);
  await fs.mkdir(directory, { mode: 0o700 });
  const lock = path.join(directory, 'vault.v2.json.node-lock');
  await fs.mkdir(lock, { mode: 0o700 });
  const token = 'd'.repeat(64);
  await fs.writeFile(path.join(lock, 'owner.json'), JSON.stringify({ pid: process.pid, token }), { mode: 0o600 });
  const result = await tool.execute({ action: 'status' }, {});
  assert.equal(result.ok, false);
  assert.equal(result.error.code, 'VAULT_BUSY');
  assert.match(result.error.message, /owned|ownership/i);
  assert.equal(result.error.reason, 'LEGACY_LIVE');
  assert.deepEqual(Object.keys(result.error).sort(), ['code', 'message', 'reason']);
  noRawDetails(result, [profile, lock, token, process.pid]);
  assert.deepEqual(JSON.parse(await fs.readFile(path.join(lock, 'owner.json'), 'utf8')), { pid: process.pid, token });
});

for (const modern of [false,true]) test(`tool classifies malformed ${modern?'modern':'legacy'} owner without raw data`, async t => {
  const {profile,tool,directory}=await fixture(t);
  await fs.mkdir(directory,{mode:0o700});
  const lock=path.join(directory,`vault.v2.json.node-${modern?'owner':'lock'}`);
  await fs.mkdir(lock,{mode:0o700});
  const marker=path.join(lock,modern?'malformed.json':'owner.json');
  await fs.writeFile(marker,'SYNTHETIC-MALFORMED-OWNER',{mode:0o600});
  const result=await tool.execute({action:'status'},{});
  assert.equal(result.error.code,'VAULT_BUSY');
  assert.equal(result.error.reason,modern?'MODERN_INVALID':'LEGACY_INVALID');
  assert.equal(await fs.readFile(marker,'utf8'),'SYNTHETIC-MALFORMED-OWNER');
  noRawDetails(result,[profile,marker,'SYNTHETIC-MALFORMED-OWNER']);
});

test('tool reports a blocked storage directory with static errno classification', async t => {
  const { profile, tool, directory } = await fixture(t);
  await fs.writeFile(directory, 'SYNTHETIC-BLOCKED-PATH', { mode: 0o600 });
  const result = await tool.execute({ action: 'status' }, {});
  assert.equal(result.ok, false);
  assert.equal(result.error.code, 'VAULT_STORAGE_ERROR');
  assert.ok(['EEXIST', 'ENOTDIR'].includes(result.error.reason));
  assert.equal(typeof result.error.message, 'string');
  assert.deepEqual(Object.keys(result.error).sort(), ['code', 'message', 'reason']);
  noRawDetails(result, [profile, directory, 'SYNTHETIC-BLOCKED-PATH', 'mkdir', 'syscall']);
});

for (const code of [undefined, 'SYNTHETIC_UNKNOWN', 'EIO', 'ENOSPC', 'EROFS']) {
  test(`tool sanitizes injected storage failure ${code ?? 'without code'}`, async t => {
    const { profile, tool } = await fixture(t);
    const originalLstat = fs.lstat;
    const secret = 'SYNTHETIC-RAW-ERROR-NEVER-PUBLISH';
    fs.lstat = async function(file, ...args) {
      if (String(file).startsWith(profile + path.sep)) {
        throw Object.assign(new Error(`${secret}: ${profile}`), { code, path: profile, syscall: 'synthetic-sensitive-syscall' });
      }
      return originalLstat.call(fs, file, ...args);
    };
    let result;
    try { result = await tool.execute({ action: 'status' }, {}); }
    finally { fs.lstat = originalLstat; }
    assert.equal(result.ok, false);
    if (['EIO', 'ENOSPC', 'EROFS'].includes(code)) {
      assert.equal(result.error.code, 'VAULT_STORAGE_ERROR');
      assert.equal(result.error.reason, code);
      assert.deepEqual(Object.keys(result.error).sort(), ['code', 'message', 'reason']);
    } else {
      assert.equal(result.error.code, 'VAULT_OPERATION_FAILED');
      assert.deepEqual(Object.keys(result.error).sort(), ['code', 'message']);
    }
    noRawDetails(result, [profile, secret, 'synthetic-sensitive-syscall', ...(code === 'SYNTHETIC_UNKNOWN' ? [code] : [])]);
  });
}
