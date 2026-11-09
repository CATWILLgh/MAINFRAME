import { CollaborationError } from './core.js';
import { readBeforeAdmission } from './lifecycle-reads.js';

const fail = (code, message) => { throw new CollaborationError(code, message); };
const text = (value, max = 512) => typeof value === 'string' && value.length > 0 && value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
const label = value => String(value ?? '').slice(0, 200);
export function requestedSelection(args, required = false) {
  const supplied = ['provider', 'model', 'reasoning_effort'].some(key => args[key] !== undefined);
  if (!supplied && !required) return undefined;
  if (!text(args.provider, 200) || !text(args.model) ||
      (args.reasoning_effort !== undefined && !text(args.reasoning_effort, 128)))
    fail('invalid-input', 'Supply exact provider and model together; reasoning_effort is optional. Discover IDs with collaboration action models.');
  return { provider: args.provider, model: args.model,
    ...(args.reasoning_effort === undefined ? {} : { reasoningEffort: args.reasoning_effort }) };
}

// Only advertised, registered routes are selectable. Resolution validates the exact
// effort, but its materialized defaults must NOT be persisted: omission means Auto.
export function createModelSelection(ctx) {
  async function catalog(provider, signal) {
    signal?.throwIfAborted();
    if (!ctx.llm.listProviders().some(item => item.id === provider))
      fail('model-unavailable', 'Provider is not currently registered. Refresh collaboration action models.');
    const models = await readBeforeAdmission(() => ctx.llm.listModels(provider), signal);
    signal?.throwIfAborted();
    return models;
  }
  async function validate(selection, signal) {
    try {
      if (!(await catalog(selection.provider, signal)).some(item => item.id === selection.model))
        fail('model-unavailable', 'Model is not in the current provider catalog. Refresh collaboration action models.');
      await readBeforeAdmission(() => ctx.llm.resolveCallConfig(selection, signal), signal);
      signal?.throwIfAborted();
      return selection;
    } catch (error) {
      signal?.throwIfAborted();
      if (error instanceof CollaborationError) throw error;
      fail('model-unavailable', 'The exact route or reasoning effort is unavailable. Refresh collaboration action models before selecting.');
    }
  }
  async function models(args = {}, signal) {
    if (!args || typeof args !== 'object' || Array.isArray(args) ||
        Object.keys(args).some(key => !['provider', 'model', 'offset', 'limit'].includes(key)))
      fail('invalid-input', 'Only provider, model, offset and limit are supported.');
    const { provider, model, offset = 0, limit = 30 } = args;
    if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isInteger(limit) || limit < 1 || limit > 100 ||
        (provider !== undefined && !text(provider, 200)) || (model !== undefined && (!provider || !text(model))))
      fail('invalid-input', 'Use a nonnegative offset, limit 1–100, and provider before model.');
    signal?.throwIfAborted();
    try {
      let kind = 'providers', entries, extra = {};
      if (provider === undefined) entries = ctx.llm.listProviders();
      else {
        entries = await catalog(provider, signal); kind = 'models'; extra.provider = provider;
        if (model !== undefined) {
          if (!entries.some(item => item.id === model)) fail('model-unavailable', 'Model is not in the current provider catalog.');
          const info = await readBeforeAdmission(() => ctx.llm.resolveModelInfo(provider, model, signal), signal);
          signal?.throwIfAborted();
          entries = info.reasoning?.efforts ?? []; kind = 'efforts';
          extra = { provider, model, auto: 'Omit reasoning_effort to use adapter defaults.',
            ...(info.reasoning?.defaultEffort === undefined ? {} : { defaultEffort: info.reasoning.defaultEffort }) };
        }
      }
      const items = entries.slice(offset, offset + limit).map(item => ({ id: item.id, name: label(item.name) }));
      return { kind, ...extra, items, total: entries.length, nextOffset: offset + items.length < entries.length ? offset + items.length : null };
    } catch (error) {
      signal?.throwIfAborted();
      if (error instanceof CollaborationError) throw error;
      fail('model-unavailable', 'Model metadata is unavailable. No selection was changed.');
    }
  }
  return { models, validate };
}
