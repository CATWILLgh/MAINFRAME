import test from 'node:test';
import {ownedEffects} from './test-effects.mjs';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { apply } from './index.js';
import { VaultStore } from './vault-store.js';

const password = 'Synthetic-host-recovery-password';
const nextPassword = 'Synthetic-host-replacement-password';
async function fixture(t, passwordOnlyNode = false) {
  const profile = await mkdtemp(path.join(os.tmpdir(), 'vault-recovery-host-synthetic-'));
  if (passwordOnlyNode) {
    const store = new VaultStore({ databasePath: path.join(profile, 'secrets-vault', 'vault.v2.json') });
    try { await store.setup(password, password); } finally { await store.dispose(); }
  }
  const peer = {};
  let route, tool;const {effect,on,dispose}=ownedEffects();
  const injections = [];
  const ctx = {
    effect,on,
    connection: { browserPeer: peer, admit: () => ({ peer }), fetch: { register: value => { route = value; return () => {}; } } },
    tools: { register: value => { tool = value; return () => {}; } },
    systemPrompt: { section: () => () => {} },
    agents: { get: () => ({ inject: value => injections.push(value) }) },
  };
  apply(ctx, { profileDirectory: profile });
  t.after(async () => {
    await dispose();
    assert.equal(path.dirname(path.resolve(profile)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(profile).startsWith('vault-recovery-host-synthetic-'));
    await rm(profile, { recursive: true });
  });
  const request = (body, headers = {}) => route.fetch(new Request('http://localhost/api/secrets-vault/ui', {
    method: 'POST', headers: { 'content-type': 'application/json', 'x-secrets-vault-ui': '1', ...headers }, body: JSON.stringify(body),
  }));
  return { ctx, tool, request, ui: async body => (await request(body)).json(), injections };
}
function noMaterial(value, keys = []) {
  const encoded = JSON.stringify(value);
  assert.ok(!encoded.includes('dsh-recovery-v1-'));
  assert.ok(!encoded.includes('recoveryKey'));
  for (const key of keys) assert.ok(!encoded.includes(key));
}

test('recovery issuance is restricted to private admitted UI, never status/list/tools/notifications', async t => {
  const { ui, request, tool, ctx, injections } = await fixture(t);
  const forbiddenInputs = ['password', 'confirmation', 'recoveryKey', 'secret', 'privateKey'];
  for (const input of forbiddenInputs) assert.equal(tool.parameters.properties[input], undefined);
  for (const action of ['setup', 'enableRecovery', 'recover', 'rotateRecovery']) assert.ok(!tool.parameters.properties.action.enum.includes(action));
  for (const headers of [{ 'x-secrets-vault-ui': '' }, { 'content-type': 'text/plain' }]) {
    assert.equal((await request({ op: 'setup', password, confirmation: password }, headers)).status, 403);
  }
  ctx.connection.admit = () => ({ peer: {} });
  assert.equal((await request({ op: 'setup', password, confirmation: password })).status, 403);
  ctx.connection.admit = () => ({ rejection: new Response(null, { status: 403 }) });
  assert.equal((await request({ op: 'setup', password, confirmation: password })).status, 403);
  ctx.connection.admit = () => ({ peer: ctx.connection.browserPeer });
  const response = await request({ op: 'setup', password, confirmation: password });
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
  const setup = await response.json();
  assert.equal(setup.ok, true);
  assert.match(setup.recoveryKey, /^dsh-recovery-v1-/);
  assert.equal(setup.recoveryAvailable, true);
  noMaterial(await ui({ op: 'status' }), [setup.recoveryKey]);
  noMaterial(await tool.execute({ action: 'status' }, {}), [setup.recoveryKey]);
  const entry = await ui({ op: 'save', sessionId: 'synthetic-session', record: {
    name: 'Synthetic host recovery entry', kind: 'token', secret: { token: 'synthetic-entry-not-real' },
  } });
  assert.equal(entry.ok, true, JSON.stringify(entry));
  noMaterial(await ui({ op: 'list' }), [setup.recoveryKey, 'synthetic-entry-not-real']);
  noMaterial(await tool.execute({ action: 'list' }, {}), [setup.recoveryKey, 'synthetic-entry-not-real']);
  noMaterial(injections, [setup.recoveryKey, 'synthetic-entry-not-real']);
  // Call execute directly too: do not rely exclusively on schema enforcement.
  for (const action of ['setup', 'enableRecovery', 'recover', 'rotateRecovery']) {
    const result = await tool.execute({ action, recoveryKey: setup.recoveryKey, password: nextPassword, confirmation: nextPassword }, {});
    assert.equal(result.ok, false);
    noMaterial(result, [setup.recoveryKey]);
  }
  await ui({ op: 'lock' });
  const recovered = await ui({ op: 'recover', recoveryKey: setup.recoveryKey, password: nextPassword, confirmation: nextPassword });
  assert.equal(recovered.ok, true);
  assert.notEqual(recovered.recoveryKey, setup.recoveryKey);
  noMaterial(await tool.execute({ action: 'status' }, {}), [setup.recoveryKey, recovered.recoveryKey]);
  noMaterial(await ui({ op: 'status' }), [setup.recoveryKey, recovered.recoveryKey]);
});

test('private rotateRecovery requires fresh password and invalidates previous code', async t => {
  const { ui } = await fixture(t);
  const setup = await ui({ op: 'setup', password, confirmation: password });
  const rejected = await ui({ op: 'rotateRecovery', password: 'wrong-password' });
  assert.equal(rejected.ok, false);
  noMaterial(rejected);
  const rotated = await ui({ op: 'rotateRecovery', password });
  assert.equal(rotated.ok, true);
  assert.match(rotated.recoveryKey, /^dsh-recovery-v1-/);
  assert.notEqual(rotated.recoveryKey, setup.recoveryKey);
  const old = await ui({ op: 'recover', recoveryKey: setup.recoveryKey, password: nextPassword, confirmation: nextPassword });
  assert.equal(old.ok, false);
  noMaterial(old);
});

test('password-only Node recovery enable remains UI-only and requires password even while already unlocked', async t => {
  const { ui, tool } = await fixture(t, true);
  assert.equal((await ui({ op: 'status' })).recoveryAvailable, false);
  assert.equal((await ui({ op: 'unlock', password })).ok, true);
  assert.equal((await ui({ op: 'enableRecovery', password: 'wrong-password' })).ok, false);
  assert.equal((await ui({ op: 'status' })).recoveryAvailable, false);
  const issued = await ui({ op: 'enableRecovery', password });
  assert.equal(issued.ok, true);
  assert.match(issued.recoveryKey, /^dsh-recovery-v1-/);
  noMaterial(await tool.execute({ action: 'status' }, {}), [issued.recoveryKey]);
  const second = await ui({ op: 'enableRecovery', password });
  assert.equal(second.ok, false);
  noMaterial(second, [issued.recoveryKey]);
});
