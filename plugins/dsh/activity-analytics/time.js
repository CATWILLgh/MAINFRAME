/* Pure browser-compatible helpers. No DOM access, timers, persistence, or content capture. */

const DAY_PRESETS = new Map([['7', 7], ['14', 14], ['28', 28]]);

function timestamp(value, name) {
  const result = value instanceof Date ? value.getTime() : value;
  if (typeof result !== 'number' || !Number.isFinite(result) ||
      !Number.isFinite(new Date(result).getTime())) {
    throw new TypeError(`${name} must be a valid finite timestamp`);
  }
  return result;
}

function midnight(value) {
  const result = new Date(value);
  result.setHours(0, 0, 0, 0);
  return result;
}

function shiftDays(date, days) {
  const result = new Date(date.getTime());
  result.setDate(result.getDate() + days);
  if (!Number.isFinite(result.getTime())) throw new RangeError('Date is out of range');
  return result;
}

function calendarDate(value, name) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new TypeError(`${name} must be a YYYY-MM-DD date`);
  }
  const [year, month, day] = value.split('-').map(Number);
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) {
    throw new RangeError(`${name} is not a valid calendar date`);
  }
  // setFullYear avoids the Date constructor's special interpretation of years 0–99.
  const date = new Date(0);
  date.setHours(0, 0, 0, 0);
  date.setFullYear(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new RangeError(`${name} is not a valid local calendar date`);
  }
  return date;
}

/**
 * Resolve a half-open millisecond range in the runtime's local calendar timezone.
 * Presets are today, yesterday, 7, 14, 28, all, and custom (numeric day presets
 * are accepted too). Day windows include today. Custom end dates are inclusive
 * calendar dates, so their exclusive boundary is the following local midnight.
 * Future boundaries clamp to now; a wholly future custom range is empty.
 * `all` requires the actual trackingSince timestamp, never an epoch fallback.
 */
export function resolveRange(preset, now, trackingSince, customStart, customEnd) {
  const current = timestamp(now, 'now');
  const today = midnight(current);
  let start;
  let end = current;
  const key = String(preset);
  if (key === 'today') {
    start = today.getTime();
  } else if (key === 'yesterday') {
    start = shiftDays(today, -1).getTime();
    end = today.getTime();
  } else if (DAY_PRESETS.has(key)) {
    start = shiftDays(today, 1 - DAY_PRESETS.get(key)).getTime();
  } else if (key === 'all') {
    start = timestamp(trackingSince, 'trackingSince');
  } else if (key === 'custom') {
    const first = calendarDate(customStart, 'customStart');
    const last = calendarDate(customEnd, 'customEnd');
    if (first.getTime() > last.getTime()) throw new RangeError('Start date must not follow end date');
    start = first.getTime();
    end = shiftDays(last, 1).getTime();
  } else {
    throw new RangeError(`Unknown range preset: ${key}`);
  }
  start = Math.min(start, current);
  end = Math.min(end, current);
  if (start > end) throw new RangeError('Start timestamp must not follow end timestamp');
  return { start, end };
}

/**
 * Pure activity state engine. Call step at most maxGapMs apart (e.g. every 15s),
 * on focus/visibility changes, and on pointerdown/keydown/wheel/scroll/touch.
 * Pass only a boolean interaction flag: never key values, targets, or text.
 *
 * step({wall: Date.now(), mono: performance.now(), focused, interaction:false})
 * returns disjoint half-open [{start,end}] integer epoch-ms intervals, each
 * <=maxGapMs. isActive() reports post-step focus/idle/discontinuity state.
 * The first focused sample and normal focus regain count as activity. A blur
 * first settles the preceding focused time, then stops counting. Hidden
 * interactions do nothing. Reading time ends exactly idleMs after activity.
 *
 * Sleep/sample gaps >maxGapMs, clock regression, or wall/monotonic disagreement
 * >clockSkewMs discard that entire gap and require a NEW focused interaction;
 * focus alone cannot restart after a discontinuity. Intervals never extend past
 * the supplied wall time or overlap previously emitted time, including after a
 * backward wall-clock change. reset() discards all session state.
 */
export function createActivityClock({ idleMs = 300000, maxGapMs = 30000, clockSkewMs = 2000 } = {}) {
  for (const [key, value] of Object.entries({ idleMs, maxGapMs, clockSkewMs })) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 ||
        (key !== 'clockSkewMs' && value === 0)) {
      throw new RangeError(`${key} must be a ${key === 'clockSkewMs' ? 'nonnegative' : 'positive'} finite number`);
    }
  }
  if (!Number.isInteger(maxGapMs)) throw new RangeError('maxGapMs must be an integer number of milliseconds');
  let previous = null;
  let lastInteraction = null;
  let needsInteraction = false;
  let emittedThrough = -Infinity;

  function reset() {
    previous = null;
    lastInteraction = null;
    needsInteraction = false;
    emittedThrough = -Infinity;
  }

  function step({ wall: inputWall, mono, focused, interaction = false }) {
    const wall = timestamp(inputWall, 'wall');
    if (typeof mono !== 'number' || !Number.isFinite(mono) || mono < 0) {
      throw new TypeError('mono must be a nonnegative finite number');
    }
    if (typeof focused !== 'boolean' || typeof interaction !== 'boolean') {
      throw new TypeError('focused and interaction must be booleans');
    }
    const sample = { wall, mono, focused };
    const intervals = [];
    if (previous === null) {
      previous = sample;
      lastInteraction = focused ? mono : null;
      return intervals;
    }
    const elapsedMono = mono - previous.mono;
    const elapsedWall = wall - previous.wall;
    const discontinuity = elapsedMono < 0 || elapsedWall < 0 ||
      elapsedMono > maxGapMs || elapsedWall > maxGapMs ||
      Math.abs(elapsedMono - elapsedWall) > clockSkewMs;
    if (discontinuity) {
      needsInteraction = true;
      lastInteraction = null;
    } else if (previous.focused && !needsInteraction && lastInteraction !== null) {
      const activeMs = Math.min(elapsedMono, Math.max(0, lastInteraction + idleMs - previous.mono));
      // Date.now() is integer but performance.now() is fractional. Anchor the
      // full sample at the current wall time; flooring previous.wall+elapsedMono
      // otherwise loses ~1ms on many input events and fragments continuous time.
      const end = Math.floor(activeMs === elapsedMono ? wall : Math.min(wall, previous.wall + activeMs));
      let start = Math.max(Math.ceil(previous.wall), emittedThrough);
      while (start < end) {
        const chunkEnd = Math.min(end, start + maxGapMs);
        intervals.push({ start, end: chunkEnd });
        emittedThrough = chunkEnd;
        start = chunkEnd;
      }
    }
    if (!focused) {
      lastInteraction = null;
    } else if (interaction) {
      lastInteraction = mono;
      needsInteraction = false;
    } else if (!previous.focused && !needsInteraction) {
      lastInteraction = mono;
    }
    previous = sample;
    return intervals;
  }

  function isActive() {
    return previous !== null && previous.focused && !needsInteraction &&
      lastInteraction !== null && previous.mono - lastInteraction < idleMs;
  }

  return { step, reset, isActive };
}
