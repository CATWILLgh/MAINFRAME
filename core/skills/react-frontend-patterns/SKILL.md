---
name: react-frontend-patterns
user-invocable: false
disable-model-invocation: true
description: "Stack-adaptive React frontend patterns — recon-driven dispatch for the Vite + React 19 + TypeScript + Tailwind v4 + TanStack Query 5 + Zod + React Hook Form stack, with FSD (Feature-Sliced Design) as the named architectural default and Boy Scout / Strangler Fig discipline for legacy. Cross-cutting: typed data boundaries (Zod), discriminated request states, server-state vs client-state separation, form-state vs server-state separation, XSS / secrets / dangerouslySetInnerHTML discipline, TypeScript strict mode. Loaded by `react-frontend-engineer` agent only; closed to main-context auto-invocation."
when_to_use: "A React frontend task is in flight inside the `react-frontend-engineer` sub-agent — implementing pages, components, forms, data fetching, API integration, or refactoring existing React / TypeScript code on a Vite SPA stack. Triggered via agent frontmatter `skills:` preload, not by direct user invocation. Out of scope: Next.js / RSC frontends (separate agent), React Native, design-system implementation."
---

# React frontend patterns — stack-adaptive entry

Preloaded into the `react-frontend-engineer` sub-agent. Provides a dispatch table from project recon to per-concern pattern files, plus universal principles applied across every Vite + React project — and the architectural stance the agent pulls projects toward.

The companion skill `shadcn` (also preloaded) owns the **UI composition layer** — which component to use, how to compose it, FieldGroup / Field markup. This skill owns the **logic layer** — state, validation, data fetching, error handling, architecture. The boundary touches on forms: form *markup* is shadcn's, form *state and validation* is here.

## How to use

1. **Recon first.** Run the script [recon.js](recon.js) — `node ~/.claude/skills/mainframe/skills/react-frontend-patterns/recon.js [project_root]` — for deterministic parse of `package.json` + lockfile + `vite.config.*` + `tsconfig*`. The script also tries `npx shadcn@latest info --json` if `components.json` is present (live truth for Tailwind version, framework, aliases). Manual fallback — [recon.md](recon.md) holds the by-hand stack-detection steps — when the script is unavailable.
2. **Refuse non-Vite stacks early.** If recon detects Next.js (`next` in deps), Remix, Astro, or React Native — surface the mismatch and exit. A separate agent will own those.
3. **Apply universal principles** (below) — they hold regardless of project size, age, or existing structure.
4. **Apply the architectural stance** (FSD + Boy Scout) — see the dedicated section. Pull toward FSD on new code; do not avalanche-refactor existing structure.
5. **Dispatch by recon outcome** — read the relevant supporting file(s) from the table. Token discipline: do not pre-read irrelevant ones.
6. **Surface tech debt as tickets, not silently work around it** — see the `surface-ticket` cross-reference at the bottom.

## Dispatch table

| Recon outcome / concern | Read this |
|---|---|
| New code organisation / where does this file live | [fsd.md](fsd.md) |
| Existing structure looks like Clean Architecture / flat / something else | [fsd.md](fsd.md) — Boy-Scout section, decide migration scope |
| Data fetching (server state, queries, mutations, pagination, optimistic updates) | [data-fetching.md](data-fetching.md) |
| Forms (RHF + Zod, validation, error display, form-state vs server-state) | [forms.md](forms.md) |
| Security / validation / secrets / dangerouslySetInnerHTML / env exposure | [safety.md](safety.md) |
| Tailwind v3 → v4 migration question | [safety.md](safety.md) §Tailwind-version + companion `shadcn` skill |
| Zod v3 → v4 migration question | [forms.md](forms.md) §Zod-version |

There is no per-framework matrix (the stack is fixed to Vite + React) and no per-state-library matrix (TanStack Query owns server state; client state defaults to React's own `useState` / Context — reach for Zustand / Jotai only when a specific need surfaces).

## Universal principles (always-on, across stacks and scales)

These apply regardless of architectural school, project size, or existing layout. They are the floor — never compromised. The umbrella `CLAUDE.md` Engineering practices (CQS, marker bans, debug residue, file / function size, no `any`, no fabricated references) apply here too, not duplicated.

### The server is canonical — clients trust nothing they receive

The frontend is a presenter, not an authority. Whatever the server sends — validate at the boundary before the type system is allowed to assume it. The umbrella rule ("data at system boundaries… is untrusted and must be validated") is the floor.

- **Inbound API response → Zod schema** at the infrastructure-layer mapper / HTTP client. Bare `as ApiResponse` casts on `fetch` results are forbidden — a static type at the boundary is not a contract, runtime validation is.
- **No business decisions on the client.** Permission checks, status transitions, computed totals — display what the server returned, do not compute or re-decide. If the UI needs to know "can this user click Approve", the server returns a `capabilities: { canApprove: true }` flag; the client renders, it does not compute.
- **Client-side form validation is a UX accelerator only.** Per MDN Form Validation: "Never trust data passed to your server from the client. Even if your form is validating correctly… a malicious user can still alter the network request". The server re-validates everything. Your Zod schema in the form is for fast feedback, not security.

### UI layer holds no business logic

A component renders, dispatches events, reads state. Business decisions live one layer below — in use-cases / model files / data-fetching hooks. The presence of a non-trivial `if` over domain rules inside a `.tsx` is a smell. The fix is to lift the rule into a typed function / hook outside the component.

### Discriminated request states — no implicit "loading" from null checks

State of any async operation is one of `{ status: 'idle' } | { status: 'loading' } | { status: 'success', data: T } | { status: 'error', error: E }`. TanStack Query exposes this natively (`status`, `error`, `data`). Do NOT replace it with "is `data` null → must be loading" heuristics — they confuse the error state with the loading state and lose the original error.

### Server state and form state are separate stores

`@tanstack/react-query` is the single source of truth for server data. `react-hook-form` is the single source of truth for the **draft** the user is currently editing. They do not duplicate. Pattern: `useQuery` fetches → `useForm({ defaultValues: data })` initialises the draft from the snapshot → `mutation.mutate(form.getValues())` on submit → `queryClient.invalidateQueries` on success refreshes the snapshot.

What is forbidden: storing the loaded server entity in form state and editing it "in place" — every change becomes a desync risk against the cache.

### TypeScript strict mode — `any` is a contract break, not a shortcut

`strict: true` is the floor; add `noUncheckedIndexedAccess`. `any` is banned by the umbrella `CLAUDE.md`. `as unknown as T` to escape a real boundary type mismatch is the same anti-pattern in disguise — fix the schema, do not cast through.

### Secrets, PII, tokens

Refresh tokens never in `localStorage` (per OWASP DOM-based XSS Prevention) — `httpOnly` cookies set by the server. Access tokens in memory only if at all possible. `VITE_*` env vars are bundled into the client — never put a secret there. PII logged to console / Sentry is a leak — whitelist what is logged, redact what is not.

### `dangerouslySetInnerHTML` is a tripwire

For sanitised, server-rendered, trusted markup — acceptable. For any user-controlled content — DOMPurify or equivalent first. The umbrella OWASP XSS Prevention Cheat Sheet is the source of truth.

## Architectural stance — FSD as the target, Boy Scout / Strangler Fig as the discipline

The agent pulls every project toward **Feature-Sliced Design (FSD)** as the named default for organising code. FSD is React-native, has authoritative documentation at [feature-sliced.design](https://feature-sliced.design), and matches React's mental model of vertical features more than horizontal layers do. Detail in [fsd.md](fsd.md).

The pull is gradual, not destructive. Two enforcement levels:

**Level 1 — universal principles** (the section above): always-on, scheme-independent. Apply in every file you touch, regardless of whether the project is on FSD, Clean Architecture, or a flat structure. A new violation here is never acceptable.

**Level 2 — architectural school**: contextual. Detect what is in place via recon. If FSD-shaped — follow it. If Clean Architecture — work within its style for in-scope edits (do not break the layering you find); write *new* features in FSD-shape where they don't conflict; surface the divergence as a ticket via [`surface-ticket`](#cross-refs) so the team has a record. If flat / ad-hoc — propose FSD as the target structure at the first touch of an area, do not impose it on the whole codebase in one PR.

**Boy Scout Rule applies to both levels**: leave the file cleaner than you found it. New code never repeats the bad pattern even if neighbours do. Existing code in your edit path gets aligned one step closer to the target — not "rewrite all".

**Strangler Fig caveat — no avalanche refactor**: a refactor touching more than 3 files OR more than 100 LOC requires surfacing the plan to the user before applying (same gate as `nestjs-backend-engineer`). Quietly migrating 20 files because "they were nearby" is forbidden.

**Tech debt outlet — surface tickets, not silent workarounds**: when you spot a problem you choose not to fix in scope — adjacent anti-pattern, postponed in-scope issue, partial implementation, deliberately deferred refactor — record it via the [`surface-ticket`](#cross-refs) skill in `docs/tickets/`. Not fixed now → ticket. Fixed inline within scope → no ticket. This is non-optional; the umbrella `CLAUDE.md` rule ("any problem you choose not to fix right now becomes a ticket") is the source.

## Out of scope

- Next.js / RSC, Remix, Astro — separate agent (frontends with a Node server in the same project, different file conventions, different rendering model).
- React Native / Expo — separate agent.
- Design-system implementation (token systems, theme generators, primitive layer of a UI library) — separate concern. This agent consumes a design system (shadcn), it does not build one.
- E2E test infrastructure (Playwright / Cypress harness setup) — out of scope; unit + integration tests in scope per [`testing-strategy`](#cross-refs).
- Build pipeline / Vite plugin authoring — out of scope; configuring an existing Vite project is fine.

## Cross-refs

- [`shadcn`](../shadcn/SKILL.md) — companion skill for UI composition. Forms touch point: markup there, state / validation here.
- [`surface-ticket`](../surface-ticket/SKILL.md) — sanctioned outlet for postponed work, adjacent issues, deferred refactors. Boy-Scout-level migration plans land here.
- [`no-suppression-markers`](../no-suppression-markers/SKILL.md) — pre-done scan for TODO / FIXME / `@ts-ignore` / `eslint-disable` / `.skip` introduced by the change.
- [`testing-strategy`](../testing-strategy/SKILL.md) — unit / integration / E2E level decision and anti-pattern check.
- [`secrets-handling`](../secrets-handling/SKILL.md) — when the work touches API keys / OAuth secrets / `VITE_*` env vars.
- [`severity-calibration`](../severity-calibration/SKILL.md) — calibrating severity on findings (do not inflate Critical).
- [`code-audit`](../code-audit/SKILL.md) — when the user asks to audit / review existing UI code.

## Sources

Per-supporting-file authoritative URLs are at the bottom of each file. Umbrella references that informed this skill:

- React 19 release notes — https://react.dev/blog/2024/12/05/react-19
- Feature-Sliced Design — https://feature-sliced.design
- TanStack Query v5 — https://tanstack.com/query/latest
- React Hook Form — https://react-hook-form.com
- Zod — https://zod.dev
- Vite — https://vite.dev
- Tailwind CSS v4 — https://tailwindcss.com
- shadcn/ui — https://ui.shadcn.com
- OWASP Cheat Sheet Series (XSS Prevention, DOM-based XSS, Input Validation) — https://cheatsheetseries.owasp.org/
- MDN Form Validation — https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation
