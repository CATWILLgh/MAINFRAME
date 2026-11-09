import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir, mkdtemp, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

/**
 * Opt-in integration test against native persistence and workspace services.
 * Never called on plugin activation. Only synthetic sessions are used, including
 * one briefly published Session with an owned native detach capability. No Agent
 * is created and no model or user-history read is requested.
 * Test logs are archived, NOT erased. Temporary directories are retained so
 * archived immutable headers never point at a directory removed by this test.
 */
export async function selfTest(ctx, move) {
  assert.equal(typeof move, 'function', 'moveSession callback is required');
  const persistence = ctx.sessionPersistence;
  const registry = ctx.workspaceRegistry;
  const root = await realpath(await mkdtemp(join(tmpdir(), 'dsh-transfer-selftest-')));
  const workspaceIds = [];
  const sessionIds = new Set();
  const errors = [];
  let result;

  async function readRaw(id) {
    const handle = await persistence.open(id, 'read');
    try {
      return {
        header: structuredClone(handle.header),
        inheritedEventCount: handle.inheritedEventCount,
        events: structuredClone((await handle.read()).events),
      };
    } finally {
      await handle.close();
    }
  }

  try {
    const sourcePath = join(root, 'source');
    const targetPath = join(root, 'target');
    await mkdir(sourcePath);
    await mkdir(targetPath);
    const source = await registry.create(sourcePath, 'Transfer self-test source');
    workspaceIds.push(source.id);
    const target = await registry.create(targetPath, 'Transfer self-test target');
    workspaceIds.push(target.id);

    const id = `session-transfer-selftest-${randomUUID()}`;
    // prepare supplies this runtime's exact header format without publishing
    // a session, invoking agent/created hooks, or opening unrelated history.
    const prepared = ctx.sessions.prepare(id, { meta: { cwd: source.path } });
    const time = Date.now();
    const events = [
      ['session/title', { title: 'Synthetic transfer test', messageSeqs: [], source: { kind: 'user' } }],
      ['working-directory/change', { cwd: source.path }],
      ['permission/preset', { preset: 'workspace-write' }],
      ['sandbox/mode', { mode: 'workspace-write' }],
      ['approval/policy', { policy: 'never' }],
    ].map(([type, data], seq) => ({ type, data, seq, time }));
    const writer = await persistence.create(prepared.header);
    sessionIds.add(id);
    try {
      await writer.append(events);
      await writer.flush();
    } finally {
      await writer.close();
    }
    await source.attachSession(id);
    // Force native replay/projection validation of the artificial fixture.
    await ctx.sessionQuery.readSession(id);
    const before = await readRaw(id);
    assert.equal(before.header.isSeeded, false);
    assert.deepEqual(before.events, events);
    assert.ok(!registry.archivedSessionIds.includes(id));

    // Native publication alone must refuse the source, even without an Agent
    // or a persistence writer. Only our exact enter() capability is released;
    // this is NOT a simulation of browser navigation closing a Host Agent.
    const published = ctx.sessions.prepare(id, {
      seed: before.events,
      meta: before.header,
    });
    const detach = ctx.sessions.enter(published);
    try {
      ctx.sessions.announce(published);
      assert.equal(ctx.sessions.get(id), published);
      assert.equal(ctx.agents.get(id), undefined, 'fixture must not create an Agent');
      await assert.rejects(async () => {
        try {
          const unexpected = await move(ctx, id, target.id);
          if (unexpected?.sessionId && unexpected.sessionId !== id) sessionIds.add(unexpected.sessionId);
        } catch (error) {
          if (error?.details?.copySessionId) sessionIds.add(error.details.copySessionId);
          throw error;
        }
      }, (error) => error?.code === 'source-open',
      'an idle published source must be refused with source-open');
      assert.ok(!registry.archivedSessionIds.includes(id), 'published refusal archived source');
      assert.deepEqual(await readRaw(id), before, 'published refusal changed source log');
      assert.ok(!target.sessionIds.some((copyId) => copyId !== id), 'published refusal attached a copy');
    } finally {
      detach();
    }
    assert.equal(ctx.sessions.get(id), undefined, 'owned native detach must release fixture');
    assert.equal(ctx.agents.get(id), undefined);
    assert.deepEqual(await readRaw(id), before, 'fixture detach changed source log');

    // Writer ownership must reject even an otherwise valid cold source.
    const held = await persistence.open(id, 'write');
    try {
      await assert.rejects(async () => {
        try {
          const unexpected = await move(ctx, id, target.id);
          if (unexpected?.sessionId && unexpected.sessionId !== id) sessionIds.add(unexpected.sessionId);
        } catch (error) {
          if (error?.details?.copySessionId) sessionIds.add(error.details.copySessionId);
          throw error;
        }
      }, 'a held source writer must prevent a transfer');
    } finally {
      await held.close();
    }
    assert.ok(!registry.archivedSessionIds.includes(id), 'refused transfer archived source');
    assert.deepEqual(await readRaw(id), before, 'refused transfer changed source log');

    let moved;
    try {
      moved = await move(ctx, id, target.id);
    } catch (error) {
      if (error?.details?.copySessionId) sessionIds.add(error.details.copySessionId);
      throw error;
    }
    assert.equal(moved?.ok, true);
    assert.equal(typeof moved.sessionId, 'string');
    sessionIds.add(moved.sessionId);
    assert.notEqual(moved.sessionId, id);
    assert.equal(moved.workspaceId, target.id);
    assert.equal(moved.copied, true);
    assert.equal(moved.sourceArchived, true);

    const copy = await readRaw(moved.sessionId);
    assert.equal(copy.header.cwd, target.path);
    assert.equal(copy.header.isSeeded, true);
    assert.equal(copy.inheritedEventCount, before.events.length);
    assert.deepEqual(copy.events.slice(0, before.events.length), before.events,
      'destination must preserve every source event exactly');
    const boundary = copy.events[before.events.length];
    assert.equal(boundary?.type, 'session/end-seed');
    assert.equal(boundary.data.inherited, true);
    for (const [index, event] of copy.events.entries()) assert.equal(event.seq, index);
    const last = (type) => copy.events.findLast((event) => event.type === type)?.data;
    assert.equal(last('working-directory/change')?.cwd, target.path);
    assert.equal(last('sandbox/mode')?.mode, 'read-only');
    assert.equal(last('approval/policy')?.policy, 'ask');
    const expectedPreset = ctx.permissionPresets.catalog().defaultOptions
      .find((option) => option.value !== 'auto' && option.value !== 'custom')?.value;
    assert.ok(expectedPreset, 'an ordinary permission preset must be available');
    assert.equal(last('permission/preset')?.preset, expectedPreset);
    assert.equal(last('session/title')?.title, 'Synthetic transfer test');
    assert.ok(target.sessionIds.includes(moved.sessionId));
    assert.ok(registry.archivedSessionIds.includes(id));
    assert.deepEqual(await readRaw(id), before, 'successful transfer changed source log');
    assert.ok(!ctx.sessions.list().some((session) => sessionIds.has(session.id)),
      'self-test must not leave any live synthetic Session');
    await ctx.sessionQuery.readSession(moved.sessionId);
    result = {
      ok: true,
      checks: ['native-fixture-replay', 'published-source-refusal', 'owned-native-detach',
        'writer-lock-refusal', 'source-unchanged',
        'exact-history-prefix', 'inherited-cut', 'safe-cwd-and-permissions',
        'native-destination-replay', 'source-archived', 'no-live-session'],
      sourceSessionId: id,
      copySessionId: moved.sessionId,
      retainedDirectory: root,
    };
  } catch (error) {
    errors.push(error);
  } finally {
    // Only inspect memberships of workspaces created by THIS invocation. This
    // also catches any duplicate created just before a reported partial error.
    for (const workspaceId of workspaceIds) {
      for (const id of registry.get(workspaceId)?.sessionIds ?? []) sessionIds.add(id);
    }
    let archivedAll = true;
    for (const id of sessionIds) {
      try {
        await registry.archiveSession(id);
      } catch (error) {
        archivedAll = false;
        errors.push(error);
      }
    }
    // Registration removal retains all logs and directories. Do it only AFTER
    // every test log is archived; preserve registrations for recovery otherwise.
    if (archivedAll) {
      for (const workspaceId of [...workspaceIds].reverse()) {
        try {
          await registry.delete(workspaceId);
        } catch (error) {
          errors.push(error);
        }
      }
    }
  }
  if (errors.length) {
    const failure = new AggregateError(errors, `Transfer self-test failed; retained directory: ${root}`);
    failure.details = { retainedDirectory: root, sessionIds: [...sessionIds], workspaceIds };
    throw failure;
  }
  return { ...result, testSessionsArchived: true, workspaceRegistrationsRemoved: true };
}
