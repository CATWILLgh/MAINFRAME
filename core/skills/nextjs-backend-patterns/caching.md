# Caching — explicit, and version-aware (Next 15)

**The load-bearing Next 15 change: what was cached by default is now dynamic by default.** `fetch`, GET Route Handlers, and the client Router Cache all require explicit opt-in. Never assume a default — confirm against current docs via Context7.

## Four cache layers

1. **Request Memoization** — in-memory, per-render-pass, automatic for identical `fetch` (dedupe, not persistence).
2. **Data Cache** — persistent, server-side. **Opt-in now:** `fetch(url, { cache: 'force-cache' })` or `next: { revalidate: N }`. (`force-cache` is NO LONGER the default in 15.)
3. **Full Route Cache** — static HTML + RSC payload for static routes; invalidated when the underlying Data Cache revalidates.
4. **Router Cache** — in-browser RSC payloads for visited segments; also not-cached-by-default in 15.

## Opting in / out

- Per fetch: `{ cache: 'force-cache' }` (persist) · `{ cache: 'no-store' }` (always fresh) · `{ next: { revalidate: 60, tags: ['posts'] } }`.
- Per segment: `export const dynamic = 'force-static' | 'force-dynamic'`; `export const revalidate = N`.
- **`use cache` directive** caches a function/component return value — **experimental, behind a config flag** (`experimental.useCache` / `dynamicIO` in Next 15; renamed `cacheComponents` in Next 16). Treat as opt-in; confirm the flag name for the project's version. `unstable_cache` still exists but is legacy.

## Invalidation

- `revalidateTag('posts')` / `revalidatePath('/blog')` purge the Data Cache + Full Route Cache on demand (call from a Server Action / Route Handler). **Tag your cached fetches** so invalidation is targeted.
- Caution: a broad `revalidatePath('/')` can thunder the origin — scope tags narrowly.

## Sources

- Caching (`force-cache` opt-in, four layers) — https://nextjs.org/docs/app/guides/caching
- `use cache` / Cache Components — https://nextjs.org/docs/app/getting-started/caching
- `revalidateTag` — https://nextjs.org/docs/app/api-reference/functions/revalidateTag
