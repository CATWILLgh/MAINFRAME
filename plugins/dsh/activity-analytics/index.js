import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// DSH installs profile bundles below profile/node_modules, including pnpm links.
// Validate package identity at each boundary; source checkouts never qualify.
function installedProfileDirectory() {
  const directory = realpathSync(fileURLToPath(new URL('.', import.meta.url)));
  let profile;
  for (let ancestor = directory; path.dirname(ancestor) !== ancestor; ancestor = path.dirname(ancestor)) {
    if (path.basename(ancestor) !== 'node_modules' || path.basename(path.dirname(path.dirname(ancestor))) === '.pnpm') continue;
    try {
      if (realpathSync(path.join(ancestor, '@mainframe', 'activity-analytics')) === directory) profile = path.dirname(ancestor);
    } catch { /* Missing or unrelated native alias is not a profile anchor. */ }
  }
  return profile; // Outermost matching alias, not pnpm's inner self-reference.
}
import { createHash } from 'node:crypto';
import { ActivityStore, CHECKPOINT_MS, InputError } from './store.js';

export const inject = ['connection', 'agents'];
export const UI_PATH = '/api/activity-analytics/ui';
const MAX_BODY_BYTES = 65_536;
const headers = {
  'content-type': 'application/json',
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff',
};
const response = (value, status = 200) => new Response(JSON.stringify(value), { status, headers });
const failure = (code, message, status) => response({ ok: false, error: { code, message } }, status);

/** Exported for synthetic Host tests; production always uses the active profile. */
export async function createHost(ctx, {
  directory,
  now = Date.now,
  schedule = callback => {
    const timer = setInterval(callback, CHECKPOINT_MS);
    timer.unref?.();
    return () => clearInterval(timer);
  },
  reportError = () => console.warn('[activity-analytics] Local persistence failed; analytics may be incomplete.'),
} = {}) {
  const store = await ActivityStore.open(directory, { now });
  // Opaque stable profile+history namespace, never expose the filesystem path.
  const queueScope = createHash('sha256').update('activity-analytics-outbox-v1\0' + path.resolve(directory) + '\0' + store.state.trackingSince).digest('hex');
  let closing = false;
  const report = () => { try { reportError(); } catch { /* Error reporting must never escape an emit handler. */ } };
  const observe = operation => {
    if (closing) return;
    // agent/status is emit, not serial: contain persistence failures explicitly.
    try { Promise.resolve(operation()).catch(report); } catch { report(); }
  };
  let stop = () => {};
  // Cordis unload awaits owned effects, not an ordinary 'dispose' event.
  // Own the open store before registering other resources (also on setup failure).
  ctx.effect(() => async () => {
    closing = true;
    try { stop(); } finally {
      try { await store.close(now()); } catch { report(); }
    }
  });
  ctx.on('agent/status', ({ agent, status }) => observe(() => store.setRunning(agent, status === 'running', now())));
  ctx.on('agent/disposed', ({ agent }) => observe(() => store.setRunning(agent, false, now())));
  // All registry entries, including children; never walk session history/backfill.
  for (const agent of ctx.agents.list()) {
    if (agent.status === 'running') observe(() => store.setRunning(agent, true, now()));
  }
  stop = schedule(() => observe(() => store.checkpoint(now())));
  ctx.effect(() => ctx.connection.fetch.register({
    path: UI_PATH,
    methods: ['POST'],
    requestBody: 'buffered',
    fetch: async request => {
      try {
        const admission = ctx.connection.admit(request);
        if ('rejection' in admission || admission.peer !== ctx.connection.browserPeer || request.headers.get('x-activity-analytics-ui') !== '1') return failure('FORBIDDEN', 'Browser admission is required.', 403);
        if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') || '')) return failure('INVALID_CONTENT_TYPE', 'Expected application/json.', 415);
        if (request.method !== 'POST') return failure('METHOD_NOT_ALLOWED', 'Expected POST.', 405);
        const declared = request.headers.get('content-length');
        if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > MAX_BODY_BYTES)) return failure('BODY_TOO_LARGE', 'Request body is too large.', 413);
        const raw = await request.text();
        if (Buffer.byteLength(raw, 'utf8') > MAX_BODY_BYTES) return failure('BODY_TOO_LARGE', 'Request body is too large.', 413);
        let args;
        try { args = JSON.parse(raw); } catch { throw new InputError('Expected JSON.'); }
        if (!args || typeof args !== 'object' || Array.isArray(args)) throw new InputError('Expected an operation object.');
        if (closing) return failure('UNAVAILABLE', 'Analytics is stopping.', 503);
        let result;
        if (args.op === 'bootstrap') result = { queueScope };
        else if (args.op === 'activity') result = await store.activity(args.intervals, args.clientId, now());
        else if (args.op === 'summary') result = await store.summary(args.start, args.end, now());
        else throw new InputError('Unsupported operation.');
        return response({ ok: true, ...result });
      } catch (error) {
        if (error instanceof InputError) return failure('INVALID_INPUT', error.message, 400);
        report();
        return failure('STORAGE_FAILED', 'Local analytics storage is unavailable.', 503);
      }
    },
  }));
  return store;
}

export async function apply(ctx, config = {}) {
  const profile = config.profileDirectory || process.env.DSH_PROFILE_DIR || installedProfileDirectory();
  if (!profile) throw new Error(`Activity Analytics requires an active profile directory; loaded module: ${import.meta.url}`);
  await createHost(ctx, { directory: path.join(profile, 'activity-analytics') });
}
