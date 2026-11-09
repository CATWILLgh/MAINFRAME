/**
 * Compact, append-only clocks for human messages and full agent turns.
 * No tool/step clocks and no system-prompt changes. Phase/provenance live in
 * source metadata; the model receives only [YYYY-MM-DD HH:mm:ss ±HH:mm].
 */
import { randomUUID } from 'node:crypto';
import Schema from '@deepseek-ai/schemastery';
import en from './locale/en.json' with { type: 'json' };
import ru from './locale/ru.json' with { type: 'json' };

export const name = 'message-time';
// Cordis validates through ~standard; DSH settings/Inspect project the native
// Schemastery graph. A plain JSON Schema is not a native plugin Config.
export const Config = Schema.object({
  enabled: Schema.boolean().default(true).description(en.config.enabled),
  includeUser: Schema.boolean().default(true).description(en.config.includeUser),
  includeAssistant: Schema.boolean().default(true).description(en.config.includeAssistant),
  includeTurnStart: Schema.boolean().default(true).description(en.config.includeTurnStart),
  timeZone: Schema.string().description(en.config.timeZone),
}).i18n({ en: en.config, ru: ru.config });
const SOURCE_KIND = 'message-time';
const IANA_TIME_ZONE = /^[A-Za-z][A-Za-z0-9_+.-]*(?:\/[A-Za-z0-9_+.-]+)*$/;

function resolveZone(value) {
  if (typeof value !== 'string' || !IANA_TIME_ZONE.test(value)) return undefined;
  try {
    return new Intl.DateTimeFormat('en-US', { timeZone: value }).resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
}

function clientZone(message) {
  return resolveZone(message?.source?.clientTimeZone);
}

export function formatStamp(time, zone) {
  if (typeof time !== 'number' || !Number.isFinite(time)) return undefined;
  const date = new Date(time);
  if (Number.isNaN(date.getTime())) return undefined;
  let formatted;
  try {
    formatted = new Intl.DateTimeFormat('en-US', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hourCycle: 'h23', timeZoneName: 'longOffset',
      ...(zone === undefined ? {} : { timeZone: zone }),
    }).formatToParts(date);
  } catch {
    return zone === undefined ? undefined : formatStamp(time, undefined);
  }
  const parts = Object.fromEntries(formatted.map(part => [part.type, part.value]));
  const offset = parts.timeZoneName.replace(/^GMT$/, 'GMT+00:00').slice(3);
  return `[${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} ${offset}]`;
}

function stampMessage(time, zone, metadata) {
  const text = formatStamp(time, zone);
  if (text === undefined) return undefined;
  return {
    id: randomUUID(), role: 'user', content: [{ type: 'text', text }],
    source: { kind: SOURCE_KIND, form: 'snapshot', ...metadata,
      ...(zone === undefined ? {} : { timeZone: zone }) },
  };
}

export function apply(ctx, config) {
  const options = { enabled: true, includeUser: true, includeAssistant: true,
    includeTurnStart: true, ...config };
  if (options.enabled === false) return;
  const fallbackZone = resolveZone(options.timeZone);
  const log = ctx.logger('message-time');
  // Derived incrementally from the durable log; isolated by Session identity,
  // restored lazily on reload/fork, and collectible when the Session goes away.
  let states = new WeakMap();
  let disposed = false;

  function stateOf(session) {
    let state = states.get(session);
    if (!state) {
      state = { cursor: 0, received: new Map(), claimed: new Set(),
        pending: { 'next-turn': [], 'next-step': [] }, zone: fallbackZone,
        startedTurn: undefined, endedTurn: undefined };
      states.set(session, state);
    }
    for (const event of session.snapshotEvents(state.cursor)) {
      state.cursor = event.seq + 1;
      if (event.type === 'agent/inbox/spliced') {
        const { target, start, removedCount = 0, inserted, outcome } = event.data;
        // Native persisted splices have normalized offsets. Keep ALL pending
        // identities (including synthetic input) to preserve those positions.
        const removed = state.pending[target].splice(start, removedCount,
          ...inserted.map(message => message.id));
        for (const id of removed) {
          // Native removal/replacement/cancel explicitly records "canceled";
          // claim removes without an outcome BEFORE pre-step runs. A pending-
          // inbox-only prune would therefore lose the original receipt time.
          if (outcome === 'canceled') {
            state.received.delete(id);
            state.claimed.delete(id);
          } else if (state.received.has(id)) state.claimed.add(id);
        }
        for (const message of inserted) {
          if (message?.source?.kind === 'user') state.received.set(message.id, event.time);
        }
      }
      if (event.type === 'turn/end') {
        // Claims rejected or aborted during async assembly may never commit a
        // user/message. Terminal turns abandon them, but not queued next work.
        for (const id of state.claimed) state.received.delete(id);
        state.claimed.clear();
      }
      if (event.type !== 'user/message' || event.surfaceOp !== 'append') continue;
      const message = event.data;
      if (message?.source?.kind === 'user') {
        state.zone = clientZone(message) ?? state.zone;
        state.received.delete(message.id);
        state.claimed.delete(message.id);
      }
      const source = message?.source;
      if (source?.kind !== SOURCE_KIND) continue;
      state.zone = resolveZone(source.timeZone) ?? state.zone;
      if (source.phase === 'turn-start') state.startedTurn = source.turn;
      if (source.phase === 'turn-end') state.endedTurn = source.turn;
    }
    return state;
  }

  ctx.on('agent/pre-step', async (payload, next) => {
    const decision = await next();
    if (disposed || decision?.kind !== 'enter') return decision;
    try {
      const state = stateOf(payload.agent.session);
      let zone = state.zone;
      const messages = [];
      for (const message of decision.messages ?? []) {
        // Replace only newly proposed verbose built-in clock messages. Never
        // remove or rewrite already committed history (including old clocks).
        if (message?.source?.kind === 'time-context') continue;
        messages.push(message);
        if (message?.source?.kind !== 'user') continue;
        zone = clientZone(message) ?? zone;
        if (options.includeUser === false) continue;
        // Inbox acceptance time, not the later time when a queue is drained.
        // If no durable inbox entry exists, use admission time as a fallback.
        const stamp = stampMessage(state.received.get(message.id) ?? Date.now(), zone,
          { phase: 'user', messageId: message.id });
        if (stamp) messages.push(stamp);
      }
      if (options.includeTurnStart !== false && state.startedTurn !== payload.turn) {
        const stamp = stampMessage(Date.now(), zone, { phase: 'turn-start', turn: payload.turn });
        if (stamp) messages.push(stamp);
      }
      return { ...decision, messages };
    } catch (error) {
      log.warn('message-time: skipped clocks: %s', String(error));
      return decision;
    }
  }, { prepend: true });

  ctx.on('session/event', (session, event) => {
    // A full completed turn, not each model message or tool step. Capture the
    // zone now; never consult another session or a later mutable zone in a job.
    if (disposed) return;
    const completed = options.includeAssistant !== false && event.type === 'turn/end' &&
      event.data?.reason?.kind === 'completed';
    // Keep an already-observed Session current even if no later step arrives.
    // Unknown sessions remain lazy unless a completion clock is needed.
    if (!completed && !states.has(session)) return;
    try {
      const state = stateOf(session);
      if (!completed) return;
      const turn = event.data.turn;
      if (state.endedTurn === turn) return;
      const stamp = stampMessage(event.time, state.zone, { phase: 'turn-end', turn });
      if (!stamp) return;
      // session/event runs inside publication; append only after it unwinds.
      queueMicrotask(() => {
        if (disposed) return;
        try {
          if (stateOf(session).endedTurn === turn) return;
          session.append('user/message', stamp, { surfaceOp: 'append' });
        } catch (error) {
          log.warn('message-time: could not stamp turn end: %s', String(error));
        }
      });
    } catch (error) {
      log.warn('message-time: skipped turn end: %s', String(error));
    }
  });
  ctx.effect(() => () => {
    disposed = true;
    states = new WeakMap();
  }, 'message-time: stop queued appends and release derived state');
}
