import { setTimeout as delay } from 'node:timers/promises';
import { CollaborationError, historyView, identifier, integer, stateView } from './core.js';

const MAX_TEXT = 32000;
const STOP_ANY = Symbol('any-terminal');
const STOP_DEADLINE = Symbol('deadline');
const NOTE = 'Newest-first session windows, not guaranteed replies or task completion. Timeout may retain an earlier sample. Only observation stops; targets are unchanged.';
const emptyOutput = () => ({ records: [], truncated: false });
const invalid = message => { throw new CollaborationError('invalid-input', message); };

// Race even a non-cooperative service against observer cancellation. Rejection
// handlers remain attached to the service promise, so late failures are consumed.
function observe(operation, signal) {
  signal.throwIfAborted();
  return new Promise((resolve, reject) => {
    const onAbort = () => { cleanup(); reject(signal.reason); };
    const cleanup = () => signal.removeEventListener('abort', onAbort);
    signal.addEventListener('abort', onAbort, { once: true });
    Promise.resolve().then(() => {
      signal.throwIfAborted();
      return operation();
    }).then(value => { cleanup(); resolve(value); }, error => { cleanup(); reject(error); });
  });
}

function outputView(value, afterSeq, maxChars) {
  // Native wait is newest-first already; enforce its assistant-only window at
  // this boundary too, without exposing arbitrary records or reasoning blocks.
  const records = value.output.records.filter(({ event }) =>
    event?.type === 'assistant/message' && event.surfaceOp === 'append' && event.seq > afterSeq)
    .sort((a, b) => b.event.seq - a.event.seq);
  const output = historyView(records, { maxChars, newestFirst: true });
  const state = stateView(value.state);
  return { state, output: { ...output, truncated: value.output.truncated || output.truncated } };
}

/**
 * Independent observer factory. Integration owns dispose() on plugin unload.
 * waitMany({targets:[{sessionId,afterSeq?}],mode?:'all'|'any',timeoutMs?}, exec?)
 * accepts exec.signal and returns per-target reason/state/output/error results.
 * Errors count as terminal observations, never as successful target execution.
 */
export function createWaitMany(ctx) {
  const lifetime = new AbortController();
  const active = new Set();

  function waitMany(args = {}, exec = {}) {
    const task = run(args, exec);
    active.add(task);
    task.then(() => active.delete(task), () => active.delete(task));
    return task;
  }

  async function run(args, exec) {
    const callerSignal = exec.signal
      ? AbortSignal.any([lifetime.signal, exec.signal]) : lifetime.signal;
    callerSignal.throwIfAborted();
    if (!Array.isArray(args.targets) || args.targets.length < 1 || args.targets.length > 8)
      invalid('targets must contain 1–8 distinct existing sessions.');
    const targets = args.targets.map(target => {
      if (!target || typeof target !== 'object' || Array.isArray(target)) invalid('Each target must contain a sessionId.');
      return { sessionId: identifier(target.sessionId),
        afterSeq: integer(target.afterSeq, -1, -1, Number.MAX_SAFE_INTEGER, 'afterSeq') };
    });
    if (new Set(targets.map(target => target.sessionId)).size !== targets.length)
      invalid('targets must contain distinct session IDs.');
    const mode = args.mode ?? 'all';
    if (mode !== 'any' && mode !== 'all') invalid('mode must be any or all.');
    const timeoutMs = integer(args.timeoutMs, 30000, 1, 120000, 'timeoutMs');
    const deadline = performance.now() + timeoutMs;
    const controller = new AbortController();
    const signal = controller.signal;
    const onAbort = () => controller.abort(callerSignal.reason);
    callerSignal.addEventListener('abort', onAbort, { once: true });
    const timer = setTimeout(() => controller.abort(STOP_DEADLINE), timeoutMs);
    const results = targets.map(target => ({ ...target, reason: 'timeout', output: emptyOutput() }));
    const maxChars = Math.floor(MAX_TEXT / targets.length);
    // Both a monotonic deadline and an explicit attempt bound protect against
    // native waits that unexpectedly return timeout immediately on every call.
    const maxAttempts = Math.ceil(timeoutMs / 10) + 1;
    let terminalCount = 0;
    try {
      await Promise.all(targets.map(async (target, index) => {
        const row = results[index];
        try {
          for (let attempt = 0; attempt < maxAttempts; attempt++) {
            signal.throwIfAborted();
            const remaining = Math.ceil(deadline - performance.now());
            if (remaining <= 0) { controller.abort(STOP_DEADLINE); return; }
            // Native timeout includes assembling its state/output snapshot.
            // Leave bounded headroom before the hard shared deadline, otherwise
            // our earlier timer systematically aborts that useful final sample.
            const reserveMs = Math.min(1000, Math.max(1, Math.ceil(remaining / 10)));
            const nativeTimeoutMs = Math.max(1, remaining - reserveMs);
            let value;
            try {
              value = await observe(() => ctx.sessionController.wait({ ...target,
                timeoutMs: nativeTimeoutMs, maxMessages: 10 }, signal), signal);
            } catch (error) {
              if (signal.aborted) throw error;
              if (error?.code !== 'session/wait-timeout') throw error;
              row.error = { code: 'session/wait-timeout', message: 'Native wait timed out before a state sample.' };
            }
            if (value) {
              signal.throwIfAborted();
              if (!['idle', 'input-required', 'timeout'].includes(value.reason))
                throw new CollaborationError('invalid-wait-result', 'Unknown native wait reason.');
              Object.assign(row, outputView(value, target.afterSeq, maxChars));
              delete row.error;
              if (performance.now() >= deadline) { controller.abort(STOP_DEADLINE); return; }
              if (value.reason !== 'timeout') {
                row.reason = value.reason;
                terminalCount++;
                if (mode === 'any') controller.abort(STOP_ANY);
                return;
              }
            }
            // A native timeout is only a window boundary, not an any-mode
            // winner. Yield with bounded backoff before retrying the same cut.
            const pause = Math.min(1000, 10 * 2 ** Math.min(attempt, 7), deadline - performance.now());
            if (pause <= 0) { controller.abort(STOP_DEADLINE); return; }
            await delay(pause, undefined, { signal });
          }
          controller.abort(STOP_DEADLINE);
        } catch (error) {
          if (signal.aborted) {
            if (signal.reason === STOP_ANY) row.reason = 'stopped';
            return;
          }
          row.reason = 'error';
          row.error = { code: typeof error?.code === 'string' ? error.code.slice(0, 100) : 'wait-failed',
            message: 'Unable to observe this session.' };
          terminalCount++;
          if (mode === 'any') controller.abort(STOP_ANY);
        }
      }));
      callerSignal.throwIfAborted();
      return { scope: 'session-window', mode,
        reason: mode === 'any' && terminalCount > 0 ? 'any' : terminalCount === targets.length ? 'all' : 'timeout',
        results, truncated: results.some(row => row.output.truncated), note: NOTE };
    } finally {
      clearTimeout(timer);
      callerSignal.removeEventListener('abort', onAbort);
      controller.abort();
    }
  }

  async function dispose() {
    lifetime.abort(new Error('Session collaboration wait-many unloaded'));
    await Promise.allSettled([...active]);
  }
  return { waitMany, dispose };
}
