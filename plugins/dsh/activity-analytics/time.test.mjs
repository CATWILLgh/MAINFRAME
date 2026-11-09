import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

// Import as ESM even when the enclosing workspace has no package.json/type.
const source = await readFile(new URL('./time.js', import.meta.url), 'utf8');
const moduleURL = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { resolveRange, createActivityClock } = await import(moduleURL);
const local = (year, month, day, hour = 0, minute = 0) => new Date(year, month - 1, day, hour, minute).getTime();
const total = intervals => intervals.reduce((sum, interval) => sum + interval.end - interval.start, 0);

function inTimezone(timezone, script) {
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', `
    import assert from 'node:assert/strict';
    const {resolveRange} = await import(${JSON.stringify(moduleURL)});
    ${script}
  `], { env: { ...process.env, TZ: timezone }, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
}

test('today, yesterday and day windows use local midnight and include today', () => {
  const now = local(2026, 11, 4, 12, 34);
  assert.deepEqual(resolveRange('today', now), { start: local(2026, 11, 4), end: now });
  assert.deepEqual(resolveRange('yesterday', now), { start: local(2026, 11, 3), end: local(2026, 11, 4) });
  for (const days of [7, 14, 28]) {
    const date = new Date(local(2026, 11, 4));
    date.setDate(date.getDate() - days + 1);
    assert.deepEqual(resolveRange(String(days), now), { start: date.getTime(), end: now });
    assert.deepEqual(resolveRange(days, now), { start: date.getTime(), end: now });
  }
});

test('all begins at trackingSince, without an epoch fallback', () => {
  const now = local(2026, 11, 4, 12);
  const since = local(2026, 10, 10, 16);
  assert.deepEqual(resolveRange('all', now, since), { start: since, end: now });
  assert.deepEqual(resolveRange('all', new Date(now), new Date(since)), { start: since, end: now });
  assert.deepEqual(resolveRange('all', now, now + 1), { start: now, end: now });
  assert.throws(() => resolveRange('all', now), /trackingSince/);
});

test('custom dates include the end calendar date and clamp future to now', () => {
  const now = local(2026, 11, 4, 12);
  assert.deepEqual(resolveRange('custom', now, null, '2026-11-01', '2026-11-02'), {
    start: local(2026, 11, 1), end: local(2026, 11, 3),
  });
  assert.deepEqual(resolveRange('custom', now, null, '2026-11-04', '2026-11-04'), {
    start: local(2026, 11, 4), end: now,
  });
  assert.deepEqual(resolveRange('custom', now, null, '2026-11-05', '2026-11-10'), { start: now, end: now });
  assert.throws(() => resolveRange('custom', now, null, '2026-11-10', '2026-11-05'), /Start date/);
});

test('calendar dates are strict, reject rollover/year zero and preserve years 1–99', () => {
  const now = local(2026, 11, 4);
  for (const invalid of ['2025-02-29', '2024-02-30', '2026-04-31', '0000-01-01',
    '2026-00-01', '2026-13-01', '2026-01-00', '2026-01-32', '2026-1-01',
    '26-01-01', '10000-01-01', '2026-01-01T00:00:00Z', ' 2026-01-01', '', null]) {
    assert.throws(() => resolveRange('custom', now, null, invalid, '2026-11-04'), String(invalid));
    assert.throws(() => resolveRange('custom', now, null, '0001-01-01', invalid), String(invalid));
  }
  for (const year of ['0001', '0099', '0100', '2000']) {
    const range = resolveRange('custom', now, null, `${year}-01-01`, `${year}-01-01`);
    assert.equal(new Date(range.start).getFullYear(), Number(year));
    assert.equal(new Date(range.end).getFullYear(), Number(year));
    assert.equal(new Date(range.end).getDate(), 2);
  }
  const leap = resolveRange('custom', now, null, '2024-02-29', '2024-02-29');
  assert.equal(new Date(leap.end).getMonth(), 2);
  assert.equal(new Date(leap.end).getDate(), 1);
});

test('unknown presets and invalid timestamps throw', () => {
  for (const now of [NaN, Infinity, -Infinity, undefined, '2026-11-04', new Date(NaN), 9e15]) {
    assert.throws(() => resolveRange('today', now), /now/);
  }
  for (const preset of [null, undefined, '', 'week', 6, {}, ['today', 'all']]) {
    assert.throws(() => resolveRange(preset, Date.now()), /Unknown range/);
  }
});

test('DST day boundaries use 23/25 hour calendar days, never fixed 24h subtraction', () => {
  inTimezone('America/New_York', `
    const now = new Date(2026, 10, 5, 12).getTime();
    for (const [day, hours] of [['2026-03-08', 23], ['2026-11-01', 25]]) {
      const r = resolveRange('custom', now, null, day, day);
      assert.equal(r.end - r.start, hours * 3600000);
    }
    const spring = new Date(2026, 2, 9, 12).getTime();
    const r = resolveRange('7', spring);
    assert.equal(r.start, new Date(2026, 2, 3).getTime());
    assert.deepEqual(resolveRange('yesterday', spring), {
      start: new Date(2026, 2, 8).getTime(), end: new Date(2026, 2, 9).getTime()
    });
  `);
});

test('non-hour offset timezone uses local dates and rejects nonexistent local date', () => {
  inTimezone('Asia/Kathmandu', `
    const now = Date.parse('2026-11-04T00:30:00Z');
    assert.equal(resolveRange('today', now).start, Date.parse('2026-11-03T18:15:00Z'));
  `);
  inTimezone('Pacific/Apia', `
    assert.throws(() => resolveRange('custom', Date.now(), null, '2011-12-30', '2011-12-30'));
  `);
});

test('first focused sample starts reading; blur settles old focus, hidden events do not count', () => {
  const clock = createActivityClock();
  const sample = (time, focused, interaction = false) => clock.step({ wall: 1000000 + time, mono: time, focused, interaction });
  assert.deepEqual(sample(0, true), []);
  assert.deepEqual(sample(10000, true), [{ start: 1000000, end: 1010000 }]);
  assert.deepEqual(sample(12000, false), [{ start: 1010000, end: 1012000 }]);
  assert.deepEqual(sample(15000, false, true), []);
  assert.deepEqual(sample(20000, true), []);
  assert.deepEqual(sample(25000, true), [{ start: 1020000, end: 1025000 }]);
  assert.deepEqual(sample(25000, false), []);
  assert.deepEqual(sample(25000, false), []);
});

test('first hidden sample does not start activity; normal focus regain does', () => {
  const clock = createActivityClock();
  assert.deepEqual(clock.step({ wall: 100, mono: 0, focused: false, interaction: true }), []);
  assert.deepEqual(clock.step({ wall: 200, mono: 100, focused: true }), []);
  assert.deepEqual(clock.step({ wall: 300, mono: 200, focused: false }), [{ start: 200, end: 300 }]);
});

test('idle tail counts exactly five minutes, then resumes only from new activity', () => {
  const clock = createActivityClock();
  const all = [];
  const step = (time, interaction = false) => clock.step({ wall: 1000000 + time, mono: time, focused: true, interaction });
  step(0);
  for (let time = 20000; time <= 320000; time += 20000) all.push(...step(time));
  assert.equal(total(all), 300000);
  assert.equal(all.at(-1).end, 1300000);
  assert.deepEqual(step(330000, true), []);
  assert.deepEqual(step(340000), [{ start: 1330000, end: 1340000 }]);
});

test('idle cutoff within a sample is exact and new interaction cannot backfill idle time', () => {
  const clock = createActivityClock({ idleMs: 25000 });
  clock.step({ wall: 100000, mono: 0, focused: true });
  assert.deepEqual(clock.step({ wall: 120000, mono: 20000, focused: true }), [{ start: 100000, end: 120000 }]);
  assert.deepEqual(clock.step({ wall: 130000, mono: 30000, focused: true, interaction: true }), [{ start: 120000, end: 125000 }]);
  assert.deepEqual(clock.step({ wall: 140000, mono: 40000, focused: true }), [{ start: 130000, end: 140000 }]);
});

test('continued interactions extend reading time without double counting', () => {
  const clock = createActivityClock({ idleMs: 20000 });
  const all = [];
  for (let time = 0; time <= 60000; time += 10000) {
    all.push(...clock.step({ wall: 100000 + time, mono: time, focused: true, interaction: time % 20000 === 0 }));
  }
  assert.equal(total(all), 60000);
  for (let i = 1; i < all.length; i++) assert.equal(all[i].start, all[i - 1].end);
});

test('sleep skips whole gap, focus alone cannot resume; explicit focused activity can', () => {
  const clock = createActivityClock();
  const step = (time, focused = true, interaction = false) => clock.step({ wall: 100000 + time, mono: time, focused, interaction });
  step(0);
  assert.equal(total(step(10000)), 10000);
  assert.deepEqual(step(50001), []);
  assert.deepEqual(step(60000), []);
  assert.deepEqual(step(65000, false, true), []);
  assert.deepEqual(step(70000, true), []);
  assert.deepEqual(step(75000, true, true), []);
  assert.deepEqual(step(80000), [{ start: 175000, end: 180000 }]);
});

test('activity arriving at wake-up may restart immediately but never counts sleep', () => {
  const clock = createActivityClock();
  clock.step({ wall: 1000, mono: 0, focused: true });
  assert.deepEqual(clock.step({ wall: 101000, mono: 100000, focused: true, interaction: true }), []);
  assert.deepEqual(clock.step({ wall: 102000, mono: 101000, focused: true }), [{ start: 101000, end: 102000 }]);
});

test('wall jumps, monotonic regression, and frozen monotonic sleep require new activity', () => {
  for (const [wall, mono] of [[20001, 10000], [999, 1000], [11000, 0], [10000, 12001], [15000, 9000]]) {
    const clock = createActivityClock();
    clock.step({ wall: 10000, mono: 10000, focused: true });
    assert.deepEqual(clock.step({ wall, mono, focused: true }), []);
    assert.deepEqual(clock.step({ wall: wall + 1000, mono: mono + 1000, focused: true }), []);
    assert.deepEqual(clock.step({ wall: wall + 2000, mono: mono + 2000, focused: true, interaction: true }), []);
    assert.equal(total(clock.step({ wall: wall + 3000, mono: mono + 3000, focused: true })), 1000);
  }
});

test('backward clock corrections never overlap already emitted intervals', () => {
  const clock = createActivityClock();
  clock.step({ wall: 100000, mono: 0, focused: true });
  assert.deepEqual(clock.step({ wall: 110000, mono: 10000, focused: true }), [{ start: 100000, end: 110000 }]);
  assert.deepEqual(clock.step({ wall: 105000, mono: 15000, focused: true, interaction: true }), []);
  assert.deepEqual(clock.step({ wall: 108000, mono: 18000, focused: true }), []);
  assert.deepEqual(clock.step({ wall: 112000, mono: 22000, focused: true }), [{ start: 110000, end: 112000 }]);
});

test('max gap and skew thresholds are inclusive, every chunk is bounded and not future', () => {
  const clock = createActivityClock();
  clock.step({ wall: 100000, mono: 0, focused: true });
  assert.deepEqual(clock.step({ wall: 130000, mono: 30000, focused: true }), [{ start: 100000, end: 130000 }]);
  const intervals = clock.step({ wall: 138000, mono: 40000, focused: true });
  assert.deepEqual(intervals, [{ start: 130000, end: 138000 }]);
  for (const interval of intervals) {
    assert.ok(interval.end <= 138000);
    assert.ok(interval.end - interval.start <= 30000);
  }
  assert.deepEqual(clock.step({ wall: 145999, mono: 50000, focused: true }), []);
});

test('reset forgets focus, idle and clock recovery state', () => {
  const clock = createActivityClock();
  clock.step({ wall: 100000, mono: 100000, focused: true });
  clock.step({ wall: 200000, mono: 200000, focused: true });
  clock.reset();
  assert.deepEqual(clock.step({ wall: 1000, mono: 0, focused: true }), []);
  assert.deepEqual(clock.step({ wall: 2000, mono: 1000, focused: false }), [{ start: 1000, end: 2000 }]);
});

test('invalid options and samples fail without corrupting state', () => {
  for (const value of [0, -1, NaN, Infinity, '10', null]) {
    assert.throws(() => createActivityClock({ idleMs: value }));
    assert.throws(() => createActivityClock({ maxGapMs: value }));
  }
  assert.doesNotThrow(() => createActivityClock({ clockSkewMs: 0 }));
  assert.throws(() => createActivityClock({ clockSkewMs: -1 }));
  const clock = createActivityClock();
  clock.step({ wall: 1000, mono: 0, focused: true });
  for (const invalid of [
    { wall: NaN, mono: 1000, focused: true },
    { wall: 2000, mono: -1, focused: true },
    { wall: 2000, mono: Infinity, focused: true },
    { wall: 2000, mono: 1000, focused: 'true' },
    { wall: 2000, mono: 1000, focused: true, interaction: 'typed content' },
  ]) assert.throws(() => clock.step(invalid));
  assert.deepEqual(clock.step({ wall: 2000, mono: 1000, focused: true }), [{ start: 1000, end: 2000 }]);
});

test('isActive reflects focus, exact idle cutoff, discontinuity, recovery and reset', () => {
  const clock = createActivityClock({ idleMs: 10000 });
  assert.equal(clock.isActive(), false);
  clock.step({ wall: 1000, mono: 0, focused: true });
  assert.equal(clock.isActive(), true);
  clock.step({ wall: 11000, mono: 10000, focused: true });
  assert.equal(clock.isActive(), false);
  clock.step({ wall: 12000, mono: 11000, focused: true, interaction: true });
  assert.equal(clock.isActive(), true);
  clock.step({ wall: 13000, mono: 12000, focused: false });
  assert.equal(clock.isActive(), false);
  clock.step({ wall: 14000, mono: 13000, focused: true });
  assert.equal(clock.isActive(), true);
  clock.step({ wall: 100000, mono: 99000, focused: true });
  assert.equal(clock.isActive(), false);
  clock.step({ wall: 101000, mono: 100000, focused: true, interaction: true });
  assert.equal(clock.isActive(), true);
  clock.reset();
  assert.equal(clock.isActive(), false);
});

test('fractional performance clocks always emit integer timestamps at idle cutoff', () => {
  const clock = createActivityClock({ idleMs: 10000 });
  clock.step({ wall: 1000, mono: 0.7, focused: true });
  const intervals = [
    ...clock.step({ wall: 6000, mono: 5000.1, focused: true }),
    ...clock.step({ wall: 12000, mono: 11000.1, focused: true }),
  ];
  for (const interval of intervals) {
    assert.ok(Number.isInteger(interval.start));
    assert.ok(Number.isInteger(interval.end));
  }
  assert.equal(intervals.at(-1).end, 11000);
  assert.throws(() => createActivityClock({ maxGapMs: 30.5 }), /integer/);
});

test('small forward wall correction cannot add time after idle or extend partial cutoff',()=>{
  const make=()=>createActivityClock({idleMs:100});
  const clock=make();clock.step({wall:100000,mono:0,focused:true});
  assert.deepEqual(clock.step({wall:100100,mono:100,focused:true}),[{start:100000,end:100100}]);
  assert.deepEqual(clock.step({wall:100300,mono:200,focused:true}),[]);assert.equal(clock.isActive(),false);
  const partial=make();partial.step({wall:100000,mono:0,focused:true});partial.step({wall:100050,mono:50,focused:true});
  assert.deepEqual(partial.step({wall:100250,mono:150,focused:true}),[{start:100050,end:100100}]);
});

test('frequent fractional monotonic input never fragments or undercounts continuous wall time', () => {
  const clock=createActivityClock();let total=0,lastEnd=100000;
  clock.step({wall:100000,mono:0.9,focused:true});
  for(let i=1;i<=100000;i++){
    const intervals=clock.step({wall:100000+i,mono:i+(i%3)/10,focused:true,interaction:true});
    for(const {start,end} of intervals){assert.equal(start,lastEnd);total+=end-start;lastEnd=end;}
  }
  assert.equal(total,100000);assert.equal(lastEnd,200000);
});

test('privacy: engine consumes only numeric clocks and boolean activity, emits only intervals', () => {
  const clock = createActivityClock();
  const sample = { wall: 1000, mono: 0, focused: true, interaction: true };
  Object.defineProperty(sample, 'text', { get() { throw new Error('Must not read content'); } });
  Object.defineProperty(sample, 'target', { get() { throw new Error('Must not read targets'); } });
  clock.step(sample);
  const intervals = clock.step({ wall: 2000, mono: 1000, focused: true });
  assert.deepEqual(Object.keys(clock).sort(), ['isActive', 'reset', 'step']);
  assert.deepEqual(Object.keys(intervals[0]).sort(), ['end', 'start']);
});
