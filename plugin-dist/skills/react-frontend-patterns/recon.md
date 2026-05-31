# Project recon — detect the stack

First step on activation. Two paths.

## Preferred: deterministic script

```bash
node ~/.claude/skills/mainframe/skills/react-frontend-patterns/recon.js [project_root]
```

Parses `package.json` + `tsconfig.json` + lockfile + `components.json`. If `components.json` is present and `shadcn` is reachable on PATH or via `npx`, the script also tries `npx shadcn@latest info --json` for live truth. Emits the RECON block to stdout deterministically.

## Manual fallback

Read `package.json` yourself. Match dependency names (lowercase) in `dependencies` + `devDependencies`:

| Category | Signal → Conclusion |
|---|---|
| Build tool / framework | `vite` → vite **(this agent's target)** / `next` → next **(bail — wrong agent)** / `@remix-run/react` → remix (bail) / `astro` → astro (bail) |
| React version | `react` major from `^19.x` / `^18.x` / `^17.x` |
| Server state | `@tanstack/react-query` major from version range |
| Client state | `zustand` / `jotai` / `valtio` / `redux` (legacy?) / none (Context-only) |
| Forms | `react-hook-form` + optional `@hookform/resolvers` |
| Validation | `zod` major (v3 vs v4) / `yup` (legacy) |
| Tailwind | `tailwindcss` major (v3 vs v4) |
| UI design system | `components.json` present → shadcn; `@radix-ui/*` direct; `@mui/material` (legacy in your stack) |
| Routing | `react-router-dom` / `@tanstack/react-router` |
| Tables | `@tanstack/react-table` |
| Animation | `motion` (Framer Motion v11+) / `framer-motion` (legacy alias) |
| HTTP | `axios` / native `fetch` only |
| Package manager | `pnpm-lock.yaml` → pnpm / `yarn.lock` → yarn / `bun.lock` → bun / `package-lock.json` → npm |
| TS strict | parse `tsconfig.json` — `strict: true`? `noUncheckedIndexedAccess: true`? |
| FSD signal | presence of `src/{pages,features,entities,widgets,shared}/` directories |
| Clean-Architecture signal | presence of `src/{presentation,application,domain,infrastructure}/` directories |

## Output block — same shape either path

```
RECON:
  package_manager: <pnpm|npm|yarn|bun|unknown>
  framework: <vite|next|remix|astro|cra|unknown>
  react: <19|18|17|unknown>
  server_state: <tanstack-query-5|tanstack-query-4|none>
  client_state: <zustand|jotai|context|redux|none>
  forms: <rhf|none>
  validation: <zod-4|zod-3|yup|none>
  tailwind: <v4|v3|none>
  design_system: <shadcn|radix-direct|mui|none>
  routing: <react-router-6|tanstack-router|none>
  tables: <tanstack-table-8|none>
  http: <axios|fetch>
  ts_strict: <true+unchecked|true|false|unknown>
  arch_signal: <fsd|clean|flat|mixed>
  shadcn_info: <inline JSON from `shadcn info --json` if available>
```

## Immediate red flags

- `next` / `@remix-run/*` / `astro` in deps — **wrong agent, bail immediately**, tell the user a Next/Remix/Astro agent is needed.
- `strict: false` in tsconfig — surface as tech debt via `surface-ticket`.
- `any` usage in repo (grep `\bany\b`) — surface as tech debt.
- Both `zod` v3 and v4 in lockfile — pick the active one, ask.
- `localStorage.setItem('token'` / `localStorage.setItem('refreshToken'` — surface as security risk per `secrets-handling`.
- `dangerouslySetInnerHTML` without DOMPurify — surface per `code-audit` if not in scope.

## When recon is ambiguous

Two state libraries declared, two routing libraries, mixed Zod versions — **ask user, do not guess**. Output `<a>+<b> (multiple — ask)` in the relevant field.
