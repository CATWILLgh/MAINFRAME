window.__ModuleLoader__.load({
  id:'@mainframe/activity-analytics',
  factory(require) {
    const React=require('react'), h=React.createElement;
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
function resolveRange(preset, now, trackingSince, customStart, customEnd) {
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
function createActivityClock({ idleMs = 300000, maxGapMs = 30000, clockSkewMs = 2000 } = {}) {
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

    /* Pure browser-compatible, synchronous interval outbox. No ambient storage/DOM access.
 *
 * The caller MUST supply a fresh, globally unique opaque instance id for EVERY
 * construction, including reloads (e.g. crypto.randomUUID()), and an authenticated
 * profile scope. Keys contain only these identifiers and a monotonic sequence;
 * values contain a version and numeric half-open epoch-ms intervals.
 *
 * v2 snapshots are immutable: each persist writes the complete current union to
 * a fresh key BEFORE removing the exact captured old snapshots. A key is never
 * reused, even after deletion or a failed/ambiguous write. Another live owner can
 * append safely by publishing a fresh key, which our captured cleanup cannot touch.
 * Absence checks defend persisted id collisions, NOT simultaneous id reuse (there
 * is no Storage CAS). Fresh ids also prevent reuse of already-deleted identities.
 *
 * Recovery reads v1 and v2. Mutable v1 records remain strictly read-only, forever
 * replayable: an old tab can change them even between a comparison and deletion.
 * Host interval union makes duplicate delivery harmless. Removal failures retry
 * on later add/ACK calls; malformed/unreadable records are preserved. Rotation
 * temporarily needs room for old AND new snapshots: quota failure never deletes
 * sources first and retains the current memory union, reported as volatile. A
 * failed write whose commit cannot be read is left untouched for the next fresh
 * recovery, not retained as an unbounded in-memory journal of failed attempts.
 * No queue cap, per-event journal, timers, leases, locks, or storage events.
 */

const OUTBOX_LEGACY_PREFIX = 'activity-analytics:outbox:v1:';
const OUTBOX_PREFIX = 'activity-analytics:outbox:v2:';
const OUTBOX_MAX_EPOCH = 8_640_000_000_000_000;
const OUTBOX_MAX_BATCH = 256;
const OUTBOX_MAX_INTERVAL = 30_000;

function outboxRange(start, end) {
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) ||
      start < 0 || end > OUTBOX_MAX_EPOCH || end <= start) {
    throw new TypeError('Expected a valid positive UNIX epoch millisecond interval.');
  }
  return [start, end];
}

function outboxUnion(intervals) {
  const result = [];
  for (const [start, end] of intervals.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const last = result[result.length - 1];
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else result.push([start, end]);
  }
  return result;
}

function outboxInput(intervals, end) {
  if (end !== undefined) return [outboxRange(intervals, end)];
  if (!Array.isArray(intervals)) throw new TypeError('Expected an array of intervals.');
  return intervals.map(value => {
    if (Array.isArray(value) && value.length === 2) return outboxRange(value[0], value[1]);
    if (value && typeof value === 'object' && !Array.isArray(value)) return outboxRange(value.start, value.end);
    throw new TypeError('Expected numeric interval endpoints.');
  });
}

function outboxSubtract(pending, acknowledged) {
  const result = [];
  let index = 0;
  for (const [start, end] of pending) {
    let cursor = start;
    while (index < acknowledged.length && acknowledged[index][1] <= cursor) index++;
    let current = index;
    while (current < acknowledged.length && acknowledged[current][0] < end) {
      const [from, until] = acknowledged[current];
      if (from > cursor) result.push([cursor, from]);
      cursor = Math.max(cursor, until);
      if (cursor >= end) break;
      current++;
    }
    if (cursor < end) result.push([cursor, end]);
    index = current;
  }
  return result;
}

function outboxRecord(raw, version) {
  const value = JSON.parse(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value) || value.version !== version ||
      Object.keys(value).some(key => key !== 'version' && key !== 'pending') || !Array.isArray(value.pending)) {
    throw new TypeError('Invalid outbox record.');
  }
  const intervals = value.pending.map(row => {
    if (!Array.isArray(row) || row.length !== 2) throw new TypeError('Invalid outbox record.');
    return outboxRange(row[0], row[1]);
  });
  return outboxUnion(intervals);
}

/**
 * add([{start,end}]) (or add(start,end)); getBatch() returns detached host-shaped
 * intervals, at most 256 of <=30000ms. ack(batch) subtracts only those exact
 * intervals from the CURRENT union, retaining any concurrently appended tail.
 * Call ack only after Host success. getPending()/pendingIntervals() return copies;
 * pendingMs() reports the union duration. onState is synchronous, including restore.
 * getState(): {pendingMs,pendingCount,durable,error,recoveryError}. Error strings
 * are generic: storage exceptions/keys/raw values never leak into UI diagnostics.
 * scope:null is intentional pre-authentication memory-only mode, touching no keys.
 */
function createOutbox({ storage = null, scope = null, id, onState } = {}) {
  if (typeof id !== 'string' || id.length === 0) throw new TypeError('A unique opaque outbox id is required.');
  if (scope !== null && (typeof scope !== 'string' || scope.length === 0)) throw new TypeError('Expected an opaque nonempty scope.');
  if (onState !== undefined && typeof onState !== 'function') throw new TypeError('onState must be a function.');
  const prefix = scope === null ? null : `${OUTBOX_PREFIX}${encodeURIComponent(scope)}:`;
  const legacyPrefix = scope === null ? null : `${OUTBOX_LEGACY_PREFIX}${encodeURIComponent(scope)}:`;
  const ownPrefix = prefix === null ? null : `${prefix}${encodeURIComponent(id)}:`;
  let sequence = 0;
  // Captured immutable identities only, never a fresh directory scan for cleanup.
  // Their intervals are covered by pending or a Host ACK, so retirement can retry.
  const snapshots = new Map();
  let pending = [];
  let durable = false;
  let error = null;
  let recoveryError = null;

  const pendingMs = () => pending.reduce((total, [start, end]) => total + (end - start), 0);
  const getPending = () => pending.map(([start, end]) => ({ start, end }));
  const getState = () => ({ pendingMs: pendingMs(), pendingCount: pending.length, durable, error, recoveryError });
  function notify() {
    // UI observer failure must not turn a successfully retained sample into loss.
    try { onState?.(getState()); } catch { /* State remains available via getState(). */ }
  }
  function persist() {
    durable = false;
    if (scope === null) return;
    let key;
    let raw;
    let attempted = false;
    try {
      if (!storage || typeof storage.getItem !== 'function' || typeof storage.setItem !== 'function' ||
          typeof storage.removeItem !== 'function') throw new TypeError('Unavailable storage.');
      if (pending.length) {
        do {
          if (sequence === Number.MAX_SAFE_INTEGER) throw new TypeError('Snapshot sequence exhausted.');
          // Consume BEFORE checking/writing: failures may have committed, and a
          // reader can already hold this identity for a later retirement.
          key = `${ownPrefix}${++sequence}`;
        } while (storage.getItem(key) !== null);
        raw = JSON.stringify({ version: 2, pending });
        attempted = true;
        storage.setItem(key, raw);
      }
    } catch {
      if (attempted) {
        try {
          const current = storage.getItem(key);
          // setItem can commit and then throw. Only confirmed, exact committed
          // snapshots need tracking. Absent keys never return (fresh ids/sequence).
          if (current === raw) snapshots.set(key, raw);
          else if (current !== null) {
            recoveryError = 'A changed saved activity record was preserved and could not be retired.';
          }
        } catch {
          // Do not accumulate full snapshots for every ambiguous failure during
          // storage outage. Leave any possible commit intact for fresh recovery.
          recoveryError = 'A failed activity write could not be checked; any saved snapshot was preserved for the next recovery.';
        }
      }
      error = 'Activity storage is unavailable; unsynced activity may only be in memory.';
      return; // No source deletion on failed/ambiguous replacement.
    }
    // Capture known old identities only after successful publication, before
    // recording its fresh key. Failed writes need not copy the retirement set.
    const captured = [...snapshots];
    if (attempted) snapshots.set(key, raw);
    let cleaned = true;
    for (const [key, raw] of captured) {
      try {
        const current = storage.getItem(key);
        if (current !== null && current !== raw) {
          // Defensive isolation for corrupted or nonconforming writers. This
          // check is NOT CAS: safety still requires immutable v2 identities.
          recoveryError = 'A changed saved activity record was preserved and could not be retired.';
        } else if (current !== null) {
          storage.removeItem(key);
        }
        snapshots.delete(key);
      } catch {
        cleaned = false; // Keep this exact identity for a later safe retry.
      }
    }
    // Pending is now fully persisted (or empty after ACK/empty recovery). A
    // cleanup failure leaves duplicate replay, not volatile unacknowledged data.
    durable = true;
    error = cleaned ? null : 'Activity is retained, but saved snapshots could not be retired; cleanup will retry.';
  }

  if (scope !== null) {
    const recovered = [];
    try {
      if (!storage || typeof storage.getItem !== 'function' || typeof storage.key !== 'function') {
        throw new TypeError('Unavailable storage.');
      }
      // Snapshot the directory BEFORE any cleanup. Racing insertions/removals can
      // skip a key; an unseen record stays untouched for a later recovery.
      const keys = new Set();
      const count = storage.length;
      if (!Number.isSafeInteger(count) || count < 0) throw new TypeError('Unavailable storage directory.');
      for (let index = 0; index < count; index++) {
        const key = storage.key(index);
        if (typeof key === 'string' && (key.startsWith(prefix) || key.startsWith(legacyPrefix))) keys.add(key);
      }
      for (const key of keys) {
        // Defensive id-collision handling also consumes observed old sequences;
        // compacting one must never make its identity available to this instance.
        if (key.startsWith(ownPrefix)) {
          const suffix = key.slice(ownPrefix.length);
          const seen = Number(suffix);
          if (/^[1-9][0-9]*$/.test(suffix) && Number.isSafeInteger(seen)) sequence = Math.max(sequence, seen);
        }
        let raw;
        try { raw = storage.getItem(key); } catch {
          recoveryError = 'Some saved activity could not be recovered; existing records were preserved.';
          continue;
        }
        if (raw === null) continue;
        try {
          const version = key.startsWith(prefix) ? 2 : 1;
          if (version === 2) {
            const suffix = key.slice(prefix.length);
            const match = /^[^:]+:([1-9][0-9]*)$/.exec(suffix);
            if (!match || !Number.isSafeInteger(Number(match[1]))) throw new TypeError('Invalid snapshot key.');
          }
          for (const interval of outboxRecord(raw, version)) recovered.push(interval);
          if (version === 2) snapshots.set(key, raw);
        } catch {
          recoveryError = 'A malformed saved activity record was preserved and could not be recovered.';
        }
      }
    } catch {
      recoveryError = 'Saved activity could not be recovered; existing records were preserved.';
    }
    pending = outboxUnion(recovered);
    persist();
  }
  notify();

  return {
    add(intervals, end) {
      const additions = outboxInput(intervals, end); // Validate atomically before mutation.
      pending = outboxUnion(pending.concat(additions));
      persist();
      notify();
    },
    getBatch() {
      const batch = [];
      for (const [start, end] of pending) {
        let cursor = start;
        while (cursor < end && batch.length < OUTBOX_MAX_BATCH) {
          const until = Math.min(end, cursor + OUTBOX_MAX_INTERVAL);
          batch.push({ start: cursor, end: until });
          cursor = until;
        }
        if (batch.length === OUTBOX_MAX_BATCH) break;
      }
      return batch;
    },
    ack(intervals) {
      const acknowledged = outboxUnion(outboxInput(intervals));
      pending = outboxSubtract(pending, acknowledged);
      persist();
      notify();
    },
    getPending,
    pendingIntervals: getPending,
    pendingMs,
    getState,
  };
}

    const NS='activityAnalytics';
    const en = {
  "7": "7 days",
  "14": "14 days",
  "28": "28 days",
  "panel": "Analytics",
  "subtitle": "Time spent here. Across every conversation.",
  "today": "Today",
  "yesterday": "Yesterday",
  "all": "All time",
  "custom": "Custom range",
  "from": "From",
  "to": "Through",
  "apply": "Apply",
  "refresh": "Refresh analytics",
  "you": "Your time",
  "agents": "Agent time",
  "youHelp": "Estimated focused-window presence, not manual work",
  "agentsHelp": "Summed across all agents, including subagents",
  "hour": "h",
  "minute": "min",
  "seconds": "Less than a minute",
  "loading": "Loading analytics…",
  "error": "Could not load analytics. Try again.",
  "activityError": "Activity has not synced. Retrying automatically; keep this window open.",
  "pending": "Waiting to save",
  "saved": "Activity saved",
  "savedAt": "Last saved",
  "volatile": "Browser backup is unavailable. Pending activity is only in memory; keep this window open until it is saved.",
  "recoveryError": "A browser backup could not be read. It was preserved, not deleted. Some earlier activity may be missing.",
  "invalid": "Choose a valid date range. The end date must not precede the start date.",
  "recording": "Tracking activity",
  "paused": "User activity paused",
  "running": "Agents running",
  "since": "Tracking since",
  "rules": "How time is counted",
  "ruleUser": "Your time estimates presence, not attention or manual work. A visible, focused DSH window starts with a 5-minute grace period even before input. Trusted interaction renews it. Typing, clicking, scrolling, touch, text input and pointer movement are detected across DSH: chats, settings, previews and sidebars. After 5 minutes without input, counting pauses, even if you are still reading. Automatic page scrolling does not renew this timer. Embedded external pages may isolate their input; see the browser limitation below.",
  "ruleAgent": "Agent time measures running tasks, including model calls, tools and waits. Parallel agents add up: three agents running for 10 minutes mean 30 agent-minutes. Detached jobs after an agent becomes idle are not included.",
  "ruleDates": "Periods use this device’s local calendar. 7, 14 and 28 days include today. The custom end date is inclusive. Tracking starts at installation; earlier activity is not reconstructed.",
  "rulePrivacy": "Only timestamps and durations are stored, not text, keys, clicks or page contents. Sleep and long timer gaps are skipped. Abrupt closure may lose the latest unsynced seconds.",
  "ruleBrowser": "The browser guest is isolated from DSH. Activity inside an external embedded page is not guaranteed to renew the 5-minute timer. No page content or browsing history is read.",
  "selected": "Selected period",
  "noData": "No recorded time in this period yet.",
  "timezone": "Local time zone",
  "second": "s"
};
const ru = {
  "7": "7 дней",
  "14": "14 дней",
  "28": "28 дней",
  "panel": "Аналитика",
  "subtitle": "Время в DSH. По всем диалогам.",
  "today": "Сегодня",
  "yesterday": "Вчера",
  "all": "Всё время",
  "custom": "Свой период",
  "from": "С",
  "to": "По",
  "apply": "Применить",
  "refresh": "Обновить аналитику",
  "you": "Ваше время",
  "agents": "Время агентов",
  "youHelp": "Оценка присутствия в окне, не ручной работы",
  "agentsHelp": "Сумма по всем агентам, включая субагентов",
  "hour": "ч",
  "minute": "мин",
  "seconds": "Меньше минуты",
  "loading": "Загружаем аналитику…",
  "error": "Не удалось загрузить аналитику. Попробуйте ещё раз.",
  "activityError": "Активность ещё не сохранена. Повторяем автоматически; не закрывайте окно.",
  "pending": "Ожидает сохранения",
  "saved": "Активность сохранена",
  "savedAt": "Последнее сохранение",
  "volatile": "Резервная очередь браузера недоступна. Несохранённое время пока только в памяти; не закрывайте окно до сохранения.",
  "recoveryError": "Резервную очередь браузера не удалось прочитать. Она не удалена. Часть прежней активности может отсутствовать.",
  "invalid": "Выберите корректный период: дата окончания не раньше даты начала.",
  "recording": "Учитываем активность",
  "paused": "Учёт вашей активности на паузе",
  "running": "Работают агенты",
  "since": "Учёт с",
  "rules": "Как считается время",
  "ruleUser": "Ваше время — оценка присутствия, а не внимания или ручной работы. Видимое окно DSH в фокусе начинает учёт с 5-минутного периода даже до первого ввода. Доверенное взаимодействие продлевает его. Ввод, клики, прокрутка, касания и движения указателя учитываются по всему DSH: в чатах, настройках, предпросмотре и боковых панелях. После 5 минут без взаимодействия учёт останавливается, даже если вы продолжаете читать. Автоматическая прокрутка не продлевает этот срок. Внешние встроенные страницы могут изолировать ввод — см. ограничение браузера ниже.",
  "ruleAgent": "Время агентов — длительность выполняемых задач, включая обращения к модели, инструменты и ожидание. Параллельные агенты суммируются: три агента по 10 минут — это 30 агент-минут. Фоновые задачи после завершения работы агента не учитываются.",
  "ruleDates": "Периоды считаются по местному календарю этого устройства. 7, 14 и 28 дней включают сегодня. Последняя дата своего периода включается целиком. Учёт начинается с установки; прошлое время не восстанавливается.",
  "rulePrivacy": "Сохраняются только отметки времени и длительности, а не тексты, клавиши, клики или содержимое страниц. Сон и длинные паузы таймера пропускаются. При аварийном закрытии последние несохранённые секунды могут потеряться.",
  "ruleBrowser": "Встроенный браузер изолирован от DSH: действия внутри внешней страницы не гарантированно обновляют 5-минутный таймер. Содержимое страниц и история посещений не читаются.",
  "selected": "Выбранный период",
  "noData": "За этот период пока нет учтённого времени.",
  "timezone": "Местный часовой пояс",
  "second": "с"
};
function registerMainframeLocale(locale, namespace, en, ru) {
  const disposers = new Map();
  let refreshing = false;
  function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      for (const { id } of locale.getSnapshot().locales) {
        const key = id.toLowerCase();
        if (!disposers.has(key)) {
          // Mark before register: it synchronously notifies snapshot subscribers.
          disposers.set(key, null);
          disposers.set(key, locale.register(namespace, id, key === 'ru' ? ru : en));
        }
      }
    } finally { refreshing = false; }
  }
  refresh();
  const unsubscribe = locale.subscribe(refresh);
  return () => {
    unsubscribe();
    for (const dispose of disposers.values()) dispose?.();
    disposers.clear();
  };
}
    const css=`
.aa-page{font:inherit;color:var(--dsw-alias-label-primary);width:100%;height:100%;min-width:0;min-height:0;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;gap:32px;padding:0 clamp(24px,4vw,48px) 48px;overflow:auto;background:var(--dsw-alias-bg-base)}
.aa-page *{box-sizing:border-box}.aa-page>header,.aa-page>section{width:100%;max-width:960px;flex:none}
.aa-header{padding-top:28px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px}[data-platform=darwin] .aa-header{padding-top:calc(28px + var(--dsh-frame-top-clearance,0px))}
.aa-title{margin:0;font-size:20px;font-weight:500;line-height:28px}.aa-muted{color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}.aa-header p{margin:4px 0 0}
.aa-button{font:inherit;font-size:13px;line-height:20px;min-height:32px;padding:5px 12px;border:.5px solid var(--dsw-alias-border-l2);border-radius:16px;background:transparent;color:var(--dsw-alias-label-primary);cursor:pointer}.aa-button:hover:not(:disabled){background:var(--dsw-alias-bg-layer-2)}.aa-button:disabled{opacity:.45;cursor:default}.aa-button[aria-pressed=true]{background:var(--dsw-alias-label-primary);color:var(--dsw-alias-bg-base);border-color:transparent}.aa-icon-button{width:32px;padding:6px;display:grid;place-items:center;flex:none}
.aa-page :is(button,input,summary):focus-visible{outline:2px solid var(--dsw-alias-brand-primary);outline-offset:3px}
.aa-presets{display:flex;gap:8px;flex-wrap:wrap}.aa-filter{display:flex;flex-direction:column;gap:16px}.aa-custom{display:flex;flex-wrap:wrap;align-items:end;gap:12px}.aa-custom label{display:flex;flex-direction:column;gap:6px;font-size:13px}.aa-custom input{font:inherit;font-size:14px;min-height:36px;padding:6px 10px;border:.5px solid var(--dsw-alias-border-l2);border-radius:10px;background:transparent;color:var(--dsw-alias-label-primary);max-width:100%}
.aa-range{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding-top:16px;border-top:.5px solid var(--dsw-alias-border-l1);margin:0}.aa-range time{font-variant-numeric:tabular-nums}
.aa-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.aa-metric{padding:24px 0;border-top:2px solid var(--dsw-alias-brand-primary);min-width:0}.aa-metric:last-child{border-color:var(--dsw-alias-label-secondary)}.aa-metric h2{font:inherit;font-size:14px;font-weight:500;line-height:22px;margin:0 0 20px}.aa-number{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;font-size:clamp(36px,5vw,56px);font-weight:500;letter-spacing:-1.5px;line-height:1.15;font-variant-numeric:tabular-nums;min-height:65px}.aa-number small{font-size:18px;font-weight:400;letter-spacing:0;margin-right:8px;color:var(--dsw-alias-label-secondary)}.aa-metric p{margin:12px 0 0}
.aa-status{display:flex;flex-wrap:wrap;gap:8px 24px;padding-top:16px;border-top:.5px solid var(--dsw-alias-border-l1)}.aa-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:7px;vertical-align:middle;background:var(--dsw-alias-state-idle-primary)}.aa-dot[data-active=true]{background:var(--dsw-alias-state-success-primary)}.aa-error{font-size:13px;color:var(--dsw-alias-state-error-primary);margin:0;line-height:20px}.aa-header>div{position:relative}.aa-subtitle{display:flex;align-items:center;gap:4px;margin-top:4px}.aa-help{display:inline-flex;flex:none}.aa-help-button{border:0;background:transparent;color:var(--dsw-alias-label-secondary);width:20px;height:20px;padding:0;display:grid;place-items:center;cursor:pointer;border-radius:4px}.aa-help-button:hover{background:var(--dsw-alias-bg-layer-2)}.aa-help-panel{position:absolute;top:calc(100% + 8px);left:0;z-index:20;width:min(420px,calc(100vw - 64px));max-height:70vh;overflow:auto;padding:16px;border:.5px solid var(--dsw-alias-border-l2);border-radius:12px;background:var(--dsw-alias-bg-base);box-shadow:0 6px 24px #0003;color:var(--dsw-alias-label-secondary);font-size:13px;line-height:20px}.aa-help-panel strong{color:var(--dsw-alias-label-primary);font-weight:500}.aa-help-panel p{margin:10px 0 0}.aa-range-meta{display:flex;flex-direction:column;gap:4px}.aa-empty{margin:0}
@media(max-width:600px){.aa-metrics{grid-template-columns:1fr;gap:8px}.aa-number{font-size:44px}.aa-metric{padding:20px 0}.aa-page{gap:24px}}
`;
    function Icon({size=20}) {return h('svg',{width:size,height:size,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('path',{d:'M4 19V12M10 19V7M16 11V3',strokeLinecap:'round'}),h('circle',{cx:17,cy:17,r:4}),h('path',{d:'M17 14.5V17l1.5 1',strokeLinecap:'round'}));}
    function Refresh(){return h('svg',{width:18,height:18,viewBox:'0 0 24 24',fill:'none',stroke:'currentColor',strokeWidth:1.6,'aria-hidden':true},h('path',{d:'M20 11a8 8 0 1 0-2 6M20 4v7h-7',strokeLinecap:'round',strokeLinejoin:'round'}));}
    function Help({t}) {
      const [hover,setHover]=React.useState(false),[focused,setFocused]=React.useState(false),[pinned,setPinned]=React.useState(false),[dismissed,setDismissed]=React.useState(false),root=React.useRef(null),id=React.useId();
      const open=!dismissed&&(hover||focused||pinned);
      React.useEffect(()=>{if(!open)return;const close=e=>{if(!root.current?.contains(e.target)){setPinned(false);setFocused(false);setHover(false);setDismissed(true);}};const key=e=>{if(e.key==='Escape'||e.key==='Tab'){setPinned(false);setDismissed(true);}};document.addEventListener('pointerdown',close,true);document.addEventListener('keydown',key,true);return()=>{document.removeEventListener('pointerdown',close,true);document.removeEventListener('keydown',key,true);};},[open]);
      return h('div',{className:'aa-help',ref:root,onMouseEnter:()=>{setHover(true);setDismissed(false);},onMouseLeave:()=>setHover(false)},h('button',{type:'button',className:'aa-help-button','aria-label':t('rules'),'aria-expanded':open,'aria-describedby':open?id:undefined,onFocus:()=>{setFocused(true);setDismissed(false);},onBlur:()=>setFocused(false),onClick:()=>{if(pinned){setPinned(false);setDismissed(true);}else{setPinned(true);setDismissed(false);}}},h('svg',{width:11,height:11,viewBox:'0 0 16 16',fill:'none',stroke:'currentColor',strokeWidth:1.3,'aria-hidden':true},h('circle',{cx:8,cy:8,r:6.3}),h('path',{d:'M8 7v4M8 4.4v.2',strokeLinecap:'round'}))),open&&h('div',{id,role:'tooltip',className:'aa-help-panel'},h('strong',null,t('rules')),['ruleUser','ruleAgent','ruleDates','rulePrivacy','ruleBrowser'].map(key=>h('p',{key},t(key)))));
    }
    async function api(body,keepalive=false) {
      const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),8000);
      try {const response=await fetch('/api/activity-analytics/ui',{method:'POST',headers:{'content-type':'application/json','x-activity-analytics-ui':'1'},body:JSON.stringify(body),signal:abort.signal,keepalive});if(!response.ok)throw new Error('request');const value=await response.json();if(value.ok!==true)throw new Error('request');return value;} finally {clearTimeout(timer);}
    }
    function createController() {
      let snapshot={active:false,syncError:false,pendingMs:0,durable:false,storageError:false,recoveryError:false,lastSavedAt:null},disposed=false,flight=null,lastPointer=-Infinity,initialized=false;
      const id=globalThis.crypto.randomUUID();
      let outbox=createOutbox({id});
      const listeners=new Set(),clock=createActivityClock();
      const publish=patch=>{snapshot={...snapshot,...patch};if(!disposed)listeners.forEach(fn=>fn());};
      const focused=()=>document.visibilityState==='visible'&&document.hasFocus();
      const queueState=()=>{const s=outbox.getState();publish({pendingMs:s.pendingMs,durable:s.durable,storageError:!!s.error,recoveryError:!!s.recoveryError});};
      async function initialize(){
        if(initialized)return;
        const {queueScope}=await api({op:'bootstrap'});
        if(typeof queueScope!=='string'||! /^[a-f0-9]{64}$/.test(queueScope))throw new Error('scope');
        let storage=null;try{storage=window.localStorage;}catch{}
        // A new durable instance must never reuse an older snapshot identity.
        const restored=createOutbox({storage,scope:queueScope,id:globalThis.crypto.randomUUID()});
        restored.add(outbox.getPending());outbox=restored;initialized=true;queueState();
      }
      function sample(interaction=false,forceInactive=false){
        if(disposed)return;
        const wall=Date.now(),mono=performance.now(),active=!forceInactive&&focused();
        const intervals=clock.step({wall,mono,focused:active,interaction});
        if(intervals.length){outbox.add(intervals);queueState();}
        if(interaction&&active)lastPointer=mono;
        const recording=clock.isActive();
        if(snapshot.active!==recording)publish({active:recording});
      }
      async function flush(keepalive=false){
        if(flight)return flight;
        flight=(async()=>{
          try{
            await initialize();
            // Drain a bounded snapshot of backlog, never an endlessly growing live tail.
            const through=outbox.getPending().at(-1)?.end;
            while(through!==undefined){
              const batch=outbox.getBatch().filter(v=>v.start<through).map(v=>({start:v.start,end:Math.min(v.end,through)}));
              if(!batch.length)break;
              const result=await api({op:'activity',intervals:batch},keepalive);
              // The Host may clip a client clock slightly ahead of its own time.
              if(!Number.isSafeInteger(result.persistedThrough))throw new Error('ack');
              const acknowledged=batch.filter(v=>v.start<result.persistedThrough).map(v=>({start:v.start,end:Math.min(v.end,result.persistedThrough)}));
              outbox.ack(acknowledged);queueState();publish({syncError:false,lastSavedAt:Date.now()});
              if(batch.some(v=>v.end>result.persistedThrough)){publish({syncError:true});return false;}
            }
            publish({syncError:false});return true;
          }catch{publish({syncError:true});queueState();return false;}
        })().finally(()=>{flight=null;});
        return flight;
      }
      return {getSnapshot:()=>snapshot,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},sample,flush,
        async summary(range){sample();await flush();return api({op:'summary',...range});},
        start(){lastPointer=performance.now();sample(true);void flush();let ticks=0;
          const interact=e=>{if(e.isTrusted===false)return;if(e.type==='scroll'){sample(false);return;}if((e.type==='pointermove'||e.type==='touchmove')&&performance.now()-lastPointer<1000)return;sample(true);};
          const change=()=>{sample(false);void flush();};
          const hide=()=>{sample(false,true);void flush(true);};
          const activityEvents=['keydown','pointerdown','pointermove','wheel','scroll','touchstart','touchmove','beforeinput','input','compositionstart','compositionupdate'];
          activityEvents.forEach(name=>window.addEventListener(name,interact,{capture:true,passive:true}));
          window.addEventListener('focus',change);window.addEventListener('blur',change);document.addEventListener('visibilitychange',change);window.addEventListener('pagehide',hide);
          const timer=setInterval(()=>{sample();if(++ticks%2===0)void flush();},5000);
          return ()=>{sample(false,true);void flush(true);disposed=true;clearInterval(timer);activityEvents.forEach(name=>window.removeEventListener(name,interact,true));window.removeEventListener('focus',change);window.removeEventListener('blur',change);document.removeEventListener('visibilitychange',change);window.removeEventListener('pagehide',hide);listeners.clear();};
        }
      };
    }
    function dateInput(now){const d=new Date(now);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
    function Page({controller,t,locale}) {
      React.useSyncExternalStore(locale.subscribe.bind(locale),locale.getSnapshot.bind(locale),locale.getSnapshot.bind(locale));
      const activity=React.useSyncExternalStore(controller.subscribe,controller.getSnapshot,controller.getSnapshot);
      const [preset,setPreset]=React.useState('today'),[from,setFrom]=React.useState(()=>dateInput(Date.now())),[to,setTo]=React.useState(()=>dateInput(Date.now())),[custom,setCustom]=React.useState(null),[data,setData]=React.useState(null),[error,setError]=React.useState(''),[busy,setBusy]=React.useState(true),[revision,setRevision]=React.useState(0);
      const tracking=React.useRef(null),view=React.useRef(0);
      React.useEffect(()=>{let live=true,loading=false;const token=++view.current;
        async function load(){if(loading)return;loading=true;setBusy(true);try{
          if(tracking.current===null){const boot=await controller.summary({start:0,end:Date.now()});tracking.current=boot.trackingSince;}
          const range=resolveRange(preset,Date.now(),tracking.current,custom?.from,custom?.to);
          const result=await controller.summary(range);
          if(live&&token===view.current){setData(result);setError('');}
        }catch{if(live&&token===view.current)setError('error');}finally{loading=false;if(live&&token===view.current)setBusy(false);}}
        setData(null);void load();const timer=setInterval(()=>void load(),15000);return()=>{live=false;clearInterval(timer);};
      },[preset,custom,revision]);
      const language=locale.getLocale().active.toLowerCase()==='ru'?'ru':'en';
      const timeZone=Intl.DateTimeFormat().resolvedOptions().timeZone;
      const formats=React.useMemo(()=>({
        date:new Intl.DateTimeFormat(language,{timeZone,day:'numeric',month:'short',year:'numeric'}),
        since:new Intl.DateTimeFormat(language,{timeZone,day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}),
        saved:new Intl.DateTimeFormat(language,{timeZone,hour:'2-digit',minute:'2-digit',second:'2-digit'}),
        pending:new Intl.NumberFormat(language,{minimumFractionDigits:1,maximumFractionDigits:1})
      }),[language,timeZone]);
      const fmt=(ts,kind)=>formats[kind].format(ts);
      function duration(ms){const total=Math.floor(ms/60000),hours=Math.floor(total/60),minutes=total%60;return h(React.Fragment,null,String(hours),h('small',null,t('hour')),String(minutes).padStart(2,'0'),h('small',null,t('minute')));}
      const metric=(key,value,help)=>h('article',{className:'aa-metric'},h('h2',null,t(key)),h('div',{className:'aa-number','aria-label':value===undefined?t('loading'):`${Math.floor(value/3600000)} ${t('hour')} ${Math.floor(value/60000)%60} ${t('minute')}`},value===undefined?'—':duration(value)),h('p',{className:'aa-muted'},t(help)),value>0&&value<60000&&h('p',{className:'aa-muted'},t('seconds')));
      return h('div',{className:'aa-page',lang:language},h('style',null,css),h('header',{className:'aa-header'},h('div',null,h('h1',{className:'aa-title'},t('panel')),h('div',{className:'aa-subtitle aa-muted'},h('span',null,t('subtitle')),h(Help,{t}))),h('button',{type:'button',className:'aa-button aa-icon-button',title:t('refresh'),'aria-label':t('refresh'),disabled:busy,onClick:()=>setRevision(v=>v+1)},h(Refresh))),
        h('section',{className:'aa-filter','aria-label':t('selected')},h('div',{className:'aa-presets'},['today','yesterday','7','14','28','all','custom'].map(key=>h('button',{key,type:'button',className:'aa-button','aria-pressed':preset===key,onClick:()=>{setError('');if(key==='custom'&&!custom)setCustom({from,to});setPreset(key);}},t(key)))),preset==='custom'&&h('form',{className:'aa-custom',onSubmit:e=>{e.preventDefault();try{resolveRange('custom',Date.now(),tracking.current??Date.now(),from,to);setCustom({from,to});setError('');}catch{setError('invalid');}}},h('label',null,t('from'),h('input',{type:'date',required:true,value:from,max:dateInput(Date.now()),onChange:e=>setFrom(e.target.value)})),h('label',null,t('to'),h('input',{type:'date',required:true,value:to,max:dateInput(Date.now()),onChange:e=>setTo(e.target.value)})),h('button',{className:'aa-button',type:'submit'},t('apply'))),h('div',{className:'aa-range aa-muted'},h('span',null,data?`${fmt(data.start,'date')} — ${fmt(Math.max(data.start,data.end-1),'date')}`:t('loading')),h('div',{className:'aa-range-meta'},h('span',null,`${t('timezone')}: ${timeZone}`),data&&h('span',null,`${t('since')} ${fmt(data.trackingSince,'since')}`)))),
        (error||activity.syncError||activity.recoveryError||(activity.pendingMs>0&&!activity.durable))&&h('section',{'aria-live':'polite'},error&&h('p',{className:'aa-error',role:'alert'},t(error)),activity.syncError&&h('p',{className:'aa-error'},t('activityError')),activity.pendingMs>0&&!activity.durable&&h('p',{className:'aa-error'},t('volatile')),activity.recoveryError&&h('p',{className:'aa-error'},t('recoveryError'))),
        h('section',{className:'aa-metrics','aria-busy':busy},metric('you',data?.userMs,'youHelp'),metric('agents',data?.agentMs,'agentsHelp')),
        h('section',{className:'aa-status aa-muted'},h('span',null,h('i',{className:'aa-dot','data-active':activity.active}),t(activity.active?'recording':'paused')),h('span',null,`${t('running')}: ${data?.runningAgents??'—'}`),h('span',{'aria-live':'polite'},activity.pendingMs>0?`${t('pending')}: ${formats.pending.format(activity.pendingMs/1000)} ${t('second')}`:activity.lastSavedAt?`${t('saved')} · ${t('savedAt')} ${fmt(activity.lastSavedAt,'saved')}`:t('loading')),data&&data.userMs===0&&data.agentMs===0&&h('p',{className:'aa-empty'},t('noData'))));
    }
    return {inject:['slots','locale'],apply(ctx){
      ctx.effect(()=>registerMainframeLocale(ctx.locale,NS,en,ru));const t=ctx.locale.bind(NS),controller=createController();
      ctx.effect(()=>controller.start());
      ctx.slots.inject('sidebar.panellist',()=>ctx.slots.register({name:'sidebar.panellist',id:'activity-analytics',order:20,label:()=>t('panel'),locale:NS},Icon));
      ctx.slots.inject('main',()=>ctx.slots.register({name:'main',key:'activity-analytics',locale:NS,inject:()=>({controller,t,locale:ctx.locale})},Page));
    }};
  }
});
