import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export const CHECKPOINT_MS = 15_000;
export const MAX_GAP_MS = 30_000;
export const MAX_BATCH = 256;
export const MAX_INTERVAL_MS = 30_000;
const MAX_FILE_BYTES = 64 * 1024 * 1024;
const APPLICATION_ID = 0x44534141;
const SCHEMA = {
  metadata: 'CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), trackingSince INTEGER NOT NULL CHECK(trackingSince>=0 AND trackingSince<=8640000000000000), updatedAt INTEGER NOT NULL CHECK(updatedAt>=trackingSince AND updatedAt<=8640000000000000)) STRICT',
  user_intervals: 'CREATE TABLE user_intervals (start INTEGER PRIMARY KEY CHECK(start>=0 AND start<=8640000000000000), end INTEGER NOT NULL CHECK(end>start AND end<=8640000000000000)) STRICT',
  agent_intervals: 'CREATE TABLE agent_intervals (start INTEGER PRIMARY KEY CHECK(start>=0 AND start<=8640000000000000), end INTEGER NOT NULL CHECK(end>start AND end<=8640000000000000), weight INTEGER NOT NULL CHECK(weight>=1 AND weight<=9007199254740991)) STRICT',
};
export class InputError extends Error {
  constructor(message) { super(message); this.name = 'InputError'; }
}
const epoch = n => Number.isSafeInteger(n) && n >= 0 && n <= 8_640_000_000_000_000;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
function range(start, end, allowEmpty = false) {
  if (!epoch(start) || !epoch(end) || (allowEmpty ? end < start : end <= start)) throw new InputError('Expected a valid UNIX epoch millisecond range.');
}
export function union(intervals) {
  const result = [];
  for (const [start, end] of intervals.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
    const last = result.at(-1);
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else result.push([start, end]);
  }
  return result;
}
function validateState(state) {
  if (!object(state) || state.version !== 1 || !epoch(state.trackingSince) || !epoch(state.updatedAt) || state.updatedAt < state.trackingSince) throw new Error('Invalid analytics state.');
  for (const [key, weighted] of [['userIntervals', false], ['agentIntervals', true]]) {
    if (!Array.isArray(state[key])) throw new Error('Invalid analytics state.');
    let previousEnd = -1;
    for (const row of state[key]) {
      if (!Array.isArray(row) || row.length !== (weighted ? 3 : 2)) throw new Error('Invalid analytics state.');
      const [start, end, count] = row;
      if (!epoch(start) || !epoch(end) || start < state.trackingSince || end <= start || end > state.updatedAt || start < previousEnd || (weighted && (!Number.isSafeInteger(count) || count < 1))) throw new Error('Invalid analytics state.');
      previousEnd = end;
    }
  }
  return state;
}
async function privateFile(file, allowMissing = false, maxBytes = Infinity, chmod = true) {
  try {
    const stat = await fs.lstat(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > maxBytes) throw new Error('Invalid analytics file.');
    if (chmod) await fs.chmod(file, 0o600);
    return true;
  } catch (error) { if (allowMissing && error.code === 'ENOENT') return false; throw error; }
}
function transaction(db, operation) {
  db.exec('BEGIN IMMEDIATE');
  try { const result = operation(); db.exec('COMMIT'); return result; }
  catch (error) { try { db.exec('ROLLBACK'); } catch {} throw error; }
}
function verifyDatabase(db) {
  if (db.prepare('PRAGMA application_id').get().application_id !== APPLICATION_ID || db.prepare('PRAGMA user_version').get().user_version !== 1) throw new Error('Unsupported analytics database schema.');
  const schema = db.prepare("SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").all();
  if (schema.length !== Object.keys(SCHEMA).length || schema.some(row => SCHEMA[row.name] !== row.sql)) throw new Error('Invalid analytics database schema.');
  const check = db.prepare('PRAGMA integrity_check').all();
  if (check.length !== 1 || check[0].integrity_check !== 'ok') throw new Error('Corrupt analytics database.');
  const metadata = db.prepare('SELECT * FROM metadata').all();
  if (metadata.length !== 1 || metadata[0].id !== 1 || !epoch(metadata[0].trackingSince) || !epoch(metadata[0].updatedAt) || metadata[0].updatedAt < metadata[0].trackingSince) throw new Error('Invalid analytics database metadata.');
  for (const table of ['user_intervals', 'agent_intervals']) {
    const invalid = db.prepare(`SELECT 1 FROM (SELECT start,end,LAG(end) OVER (ORDER BY start) AS previousEnd FROM ${table}) WHERE start < ? OR end > ? OR start ${table === 'user_intervals' ? '<=' : '<'} previousEnd LIMIT 1`).get(metadata[0].trackingSince, metadata[0].updatedAt);
    if (invalid) throw new Error('Invalid analytics database intervals.');
  }
  return { version: 1, trackingSince: metadata[0].trackingSince, updatedAt: metadata[0].updatedAt };
}

/** One Host writer; numeric rows only. Historical rows stay in SQLite, never in the live heap. */
export class ActivityStore {
  static async open(directory, { now = Date.now } = {}) {
    const store = new ActivityStore(directory, now);
    // A descriptive failure instead of silently choosing a second storage backend.
    let DatabaseSync;
    try { ({ DatabaseSync } = await import('node:sqlite')); }
    catch { throw new Error('Activity Analytics requires a Node runtime with node:sqlite DatabaseSync.'); }
    await fs.mkdir(store.directory, { recursive: true, mode: 0o700 });
    const info = await fs.lstat(store.directory);
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error('Analytics directory must be a private real directory.');
    await fs.chmod(store.directory, 0o700);
    if (!await privateFile(store.file, true)) {
      let state;
      if (await privateFile(store.legacyFile, true, MAX_FILE_BYTES, false)) state = validateState(JSON.parse(await fs.readFile(store.legacyFile, 'utf8')));
      else { const time = store.time(); state = { version: 1, trackingSince: time, updatedAt: time, userIntervals: [], agentIntervals: [] }; }
      // Build privately, commit everything, close/fsync, then publish without replacing an existing DB.
      // The original JSON is never renamed, rewritten, or deleted. A crash before publication retries import.
      const temporary = path.join(store.directory, `.intervals-${randomUUID()}.sqlite.tmp`);
      let db;
      try {
        const handle = await fs.open(temporary, 'wx', 0o600); await handle.close();
        db = new DatabaseSync(temporary);
        db.exec('PRAGMA synchronous=FULL; PRAGMA journal_mode=DELETE');
        transaction(db, () => {
          for (const sql of Object.values(SCHEMA)) db.exec(sql);
          db.exec(`PRAGMA application_id=${APPLICATION_ID}; PRAGMA user_version=1`);
          db.prepare('INSERT INTO metadata VALUES (1,?,?)').run(state.trackingSince, state.updatedAt);
          const users = db.prepare('INSERT INTO user_intervals VALUES (?,?)');
          for (const row of union(state.userIntervals)) users.run(...row);
          const agents = db.prepare('INSERT INTO agent_intervals VALUES (?,?,?)');
          for (const row of state.agentIntervals) agents.run(...row);
        });
        verifyDatabase(db);
        db.close(); db = undefined;
        const handle2 = await fs.open(temporary, 'r'); try { await handle2.sync(); } finally { await handle2.close(); }
        try { await fs.link(temporary, store.file); } catch (error) { if (error.code !== 'EEXIST') throw error; }
        const parent = await fs.open(store.directory, 'r'); try { await parent.sync(); } finally { await parent.close(); }
      } finally {
        db?.close();
        // Exact UUID child created above, not user-controlled/computed external paths.
        await fs.unlink(temporary).catch(error => { if (error.code !== 'ENOENT') throw error; });
        await fs.unlink(`${temporary}-journal`).catch(error => { if (error.code !== 'ENOENT') throw error; });
      }
    }
    await privateFile(store.file);
    for (const suffix of ['-wal', '-shm', '-journal']) await privateFile(`${store.file}${suffix}`, true);
    try {
      store.db = new DatabaseSync(store.file);
      store.db.exec('PRAGMA busy_timeout=1000; PRAGMA trusted_schema=OFF');
      store.state = verifyDatabase(store.db); // Full startup validation only; operations use indexed range statements.
      store.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL');
      store.prepare();
      store.cursor = Math.max(store.time(), store.state.updatedAt);
      return store;
    } catch (error) { store.db?.close(); throw error; }
  }
  constructor(directory, now) {
    this.directory = path.resolve(directory);
    this.file = path.join(this.directory, 'intervals.sqlite');
    this.legacyFile = path.join(this.directory, 'intervals.json');
    this.now = now;
    this.active = new Set(); // Exact live Agent objects, never serialized.
    this.pendingUsers = [];
    this.pendingAgents = [];
    this.serial = Promise.resolve();
    this.closed = false;
    this.closing = false;
    this.disposal = undefined;
    this.dirty = false;
  }
  prepare() {
    this.sql = {};
    for (const table of ['user_intervals', 'agent_intervals']) {
      this.sql[table] = {
        predecessor: this.db.prepare(`SELECT * FROM ${table} WHERE start<=? ORDER BY start DESC LIMIT 1`),
        // PK start is a B-tree index. The predecessor bounds the only possibly overlapping older row.
        total: this.db.prepare(`SELECT TOTAL((MIN(end,?)-MAX(start,?))${table === 'agent_intervals' ? '*weight' : ''}) AS total FROM ${table} WHERE start>=? AND start<? AND end>?`),
      };
    }
    this.sql.userBounds = this.db.prepare('SELECT MIN(start) AS start,MAX(end) AS end FROM user_intervals WHERE start>=? AND start<=? AND end>=?');
    this.sql.userDelete = this.db.prepare('DELETE FROM user_intervals WHERE start>=? AND start<=? AND end>=?');
    this.sql.userInsert = this.db.prepare('INSERT INTO user_intervals VALUES (?,?)');
    this.sql.agentLast = this.db.prepare('SELECT * FROM agent_intervals ORDER BY start DESC LIMIT 1');
    this.sql.agentExtend = this.db.prepare('UPDATE agent_intervals SET end=? WHERE start=?');
    this.sql.agentInsert = this.db.prepare('INSERT INTO agent_intervals VALUES (?,?,?)');
    this.sql.metadata = this.db.prepare('UPDATE metadata SET updatedAt=MAX(updatedAt,?) WHERE id=1');
  }
  time() {
    const time = this.now();
    if (!epoch(time)) throw new Error('Invalid host clock.');
    return time;
  }
  run(operation) {
    // Close admission synchronously; work accepted before close still drains.
    if (this.closing || this.closed) return Promise.reject(new Error('Analytics store is closing or closed.'));
    const result = this.serial.then(async () => {
      if (this.closed) throw new Error('Analytics store is closed.');
      return operation();
    });
    this.serial = result.then(() => {}, () => {});
    return result;
  }
  async persist() {
    transaction(this.db, () => {
      for (const [start, end] of this.pendingUsers) {
        const previous = this.sql.user_intervals.predecessor.get(start);
        const lower = previous?.end >= start ? previous.start : start;
        const bounds = this.sql.userBounds.get(lower, end, start);
        this.sql.userDelete.run(lower, end, start);
        this.sql.userInsert.run(bounds.start === null ? start : Math.min(start, bounds.start), bounds.end === null ? end : Math.max(end, bounds.end));
      }
      for (const [start, end, weight] of this.pendingAgents) {
        const last = this.sql.agentLast.get();
        if (last && last.end > start) throw new Error('Overlapping agent history: only one Host writer is supported.');
        if (last && last.end === start && last.weight === weight) this.sql.agentExtend.run(end, last.start);
        else this.sql.agentInsert.run(start, end, weight);
      }
      this.sql.metadata.run(this.state.updatedAt);
    });
  }
  async flush() {
    if (!this.dirty) return;
    await this.persist();
    this.pendingUsers = []; this.pendingAgents = []; this.dirty = false;
  }
  advance(time) {
    const end = Math.max(this.cursor, time);
    const gap = end - this.cursor;
    // A delayed tick indicates sleep/stall; discard the whole uncertain gap.
    if (gap > 0 && gap <= MAX_GAP_MS && this.active.size) {
      const last = this.pendingAgents.at(-1);
      if (last && last[1] === this.cursor && last[2] === this.active.size) last[1] = end;
      else this.pendingAgents.push([this.cursor, end, this.active.size]);
      this.dirty = true;
    }
    this.cursor = end;
    this.state.updatedAt = Math.max(this.state.updatedAt, end);
  }
  setRunning(agent, running, time = this.time()) {
    return this.run(async () => {
      this.advance(time);
      if (running) this.active.add(agent); else this.active.delete(agent);
      await this.flush();
    });
  }
  checkpoint(time = this.time()) {
    return this.run(async () => { this.advance(time); await this.flush(); });
  }
  activity(intervals, clientId, time = this.time()) {
    return this.run(async () => {
      if (!Array.isArray(intervals) || intervals.length > MAX_BATCH) throw new InputError(`At most ${MAX_BATCH} intervals are accepted.`);
      if (clientId !== undefined && (typeof clientId !== 'string' || !/^[a-zA-Z0-9._:-]{1,128}$/.test(clientId))) throw new InputError('Invalid client ID.');
      const accepted = [];
      for (const value of intervals) {
        if (!object(value) || Object.keys(value).some(key => key !== 'start' && key !== 'end')) throw new InputError('Invalid interval.');
        range(value.start, value.end);
        if (value.end - value.start > MAX_INTERVAL_MS || value.end > time + MAX_GAP_MS) throw new InputError('Activity intervals must be at most 30 seconds and not in the future.');
        const start = Math.max(value.start, this.state.trackingSince);
        const end = Math.min(value.end, time);
        if (end > start) accepted.push([start, end]);
      }
      this.advance(time);
      this.pendingUsers = union([...this.pendingUsers, ...accepted]);
      this.dirty ||= accepted.length > 0;
      await this.flush();
      return { accepted: accepted.length, trackingSince: this.state.trackingSince, persistedThrough: time };
    });
  }
  total(table, start, end) {
    const previous = this.sql[table].predecessor.get(start);
    const lower = previous?.end > start ? previous.start : start;
    return this.sql[table].total.get(end, start, lower, end, start).total;
  }
  summary(start, end, time = this.time()) {
    return this.run(async () => {
      range(start, end, true);
      this.advance(time);
      await this.flush();
      const from = Math.max(start, this.state.trackingSince);
      const until = Math.min(end, time);
      return {
        start, end,
        userMs: until > from ? this.total('user_intervals', from, until) : 0,
        agentMs: until > from ? this.total('agent_intervals', from, until) : 0,
        trackingSince: this.state.trackingSince, asOf: time,
        runningAgents: this.active.size, checkpointMs: CHECKPOINT_MS, maxGapMs: MAX_GAP_MS,
      };
    });
  }
  close(time = this.time()) {
    if (this.disposal) return this.disposal;
    this.closing = true;
    this.disposal = this.serial.then(async () => {
      try {
        this.advance(time);
        // Only local SQLite transactions are retried. Failed transactions roll
        // back; this is bounded even if storage stays unavailable on unload.
        try { await this.flush(); } catch { await this.flush(); }
      } finally {
        this.active.clear();
        try { this.db.close(); } finally { this.closed = true; }
      }
    });
    this.serial = this.disposal.then(() => {}, () => {});
    return this.disposal;
  }
}
