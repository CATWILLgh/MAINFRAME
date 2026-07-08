# Recon — manual fallback

When `recon.js` is unavailable, detect by hand from `package.json` + the file tree and emit the `RECON:` block.

## Dimensions

- **next_version** — `dependencies.next` (e.g. `15.x`). Caching defaults hinge on 14 vs 15.
- **router** — `app/` (or `src/app/`) present → `app`; only `pages/` → `pages` (legacy); both → `mixed` (flag).
- **package_manager** — lockfile: `pnpm-lock.yaml` / `bun.lockb` / `yarn.lock` / `package-lock.json`.
- **orm** — `@prisma/client` / `prisma` → prisma; `drizzle-orm` → drizzle; else flag.
- **auth** — `next-auth` (v5 if `^5` / `beta` / `next`) / `@clerk/nextjs` / `lucia` / none.
- **validation** — `zod` / `valibot` / none.
- **ts_strict** — `tsconfig.json` `compilerOptions.strict`.

## Output

```
RECON:
  next_version: 15.1.0
  router: app
  package_manager: pnpm
  orm: prisma
  auth: next-auth@5
  validation: zod
  ts_strict: true
```

Ambiguity (mixed router, two auth libs, both prisma + drizzle, no `next` in deps) → surface and ask; do not guess.
