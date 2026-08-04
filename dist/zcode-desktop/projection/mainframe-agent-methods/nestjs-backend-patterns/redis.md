# Redis patterns — cache, lock, rate-limit (what breaks in production)

The recurring failures: caches that never expire, stampedes when a hot key expires, locks that aren't safe under clock drift, rate limiters that race. The patterns are client-agnostic — `ioredis` / `node-redis` calls differ only trivially.

## Caching

- **Cache-aside** (check cache → miss → load DB → set with TTL) is the default. **Every cache key gets a TTL.** Under a `volatile-*` eviction policy a key with no TTL is invisible to eviction and leaks until OOM (per Redis: good use of expiry keeps you off the memory limit). For a pure cache prefer `allkeys-lru` (can evict any key); use `noeviction` only when Redis is a source of truth.
- **Invalidation:** write the DB first, *then* delete the cache key — never delete-before-write (a concurrent reader repopulates stale data before the write commits).
- **Stampede** (hot key expires, all readers recompute at once): guard the recompute with a per-key lock (singleflight) and/or jitter TTLs (`base + rand(jitter)`) so related keys don't expire together.

## Distributed lock

Acquire with `SET key <random-token> NX PX <ttl>`; release with an atomic Lua check-and-del — a plain `DEL` can delete another client's lock:

```lua
if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end
```

**Know the limit (Kleppmann vs Redlock):** Redis TTL uses a wall clock, not monotonic — a clock shift or a long GC pause can let two clients hold the "same" lock. Redlock (majority of N nodes) does not fix this and emits no fencing token. So Redis locks are fine for **efficiency** (dedup work, avoid double-send); for **correctness** (money, once-only mutations) use a system with fencing tokens (etcd / ZooKeeper). Redis's own docs say to add fencing tokens for long operations.

## Rate limiting & atomicity

- Counter ops must be atomic: a non-atomic `INCR` then `EXPIRE` can lose the `EXPIRE` (process dies between) → the counter never resets and blocks the key forever. Do it in one Lua script (or `SET key 1 NX EX ttl` on first hit). Sliding-window (sorted set: `ZADD` / `ZREMRANGEBYSCORE` / `ZCARD`) and token-bucket also need Lua.
- **Lua over `MULTI`/`EXEC`** for any check-then-act: Lua runs atomically and can branch on read results; `MULTI` cannot branch and does not abort siblings on a single command error. Use `WATCH` + `MULTI` only for optimistic CAS — and then you must retry on abort.

## Persistence by role

Cache role → RDB snapshots are fine (losing cached data is acceptable). Lock / counter / session role (source of truth) → enable AOF (`appendfsync everysec`); without it a restart loses state and a "free" lock may actually be held. After a crash, delay rejoin ≥ lock TTL so held locks expire first.

## Sources

- Redis — key eviction / distributed locks — https://redis.io/docs/latest/develop/reference/eviction/
- Kleppmann, "How to do distributed locking" — https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
