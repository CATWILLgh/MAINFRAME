# Feature-Sliced Design — applied

The agent's architectural target. Defaults to FSD on **new** code; tolerates existing schemes per the Boy Scout block in [SKILL.md](SKILL.md). Authoritative source: https://feature-sliced.design.

## Layers (top → bottom)

```
src/
  app/        — composition root: providers, router, store, entry point
  pages/      — route-level compositions (one page = one route)
  widgets/    — large, page-independent UI blocks (Sidebar, Header)
  features/   — user-facing capabilities (auth/login, cart/add-item)
  entities/   — business entities (user, product, order) — model + minimal UI
  shared/     — reusable across everything (ui kit, api client, lib, config)
```

## Slice shape

Inside each layer (except `shared` and `app`), code is grouped by **slice**:

```
features/auth-login/
  ui/        — components for this feature
  model/     — state (query hooks, store, derived selectors)
  api/       — data-access for this feature (fetchers, mutations)
  lib/       — pure helpers used by this slice only
  index.ts   — PUBLIC API of the slice (only this is importable from outside)
```

`index.ts` is the contract. **External imports go through it only**, never deep into `features/auth-login/model/store.ts`.

## Dependency direction — top imports bottom, never reverse

`app → pages → widgets → features → entities → shared`. Bottom layers MUST NOT import upper ones. `entities/user` cannot import `features/auth-login`. `shared/ui/button` cannot import anything outside `shared`.

Same-layer imports between slices are forbidden too — `features/cart` cannot import from `features/auth-login`. If they share, the shared bit moves down to `entities` or `shared`.

## When the project is on Clean Architecture or flat

- **Clean Architecture** — leave the layering intact for in-scope files; new features go into FSD-shaped slices only when they don't break the existing dependency rule. Mismatch surfaced via `surface-ticket` as architectural tech debt — do not silently bridge the two schemes inside one file.
- **Flat** (`src/components`, `src/hooks`, `src/api`) — propose FSD at the **first touch of a domain area** (e.g. when adding the second auth-related component). Do not migrate the whole tree in one PR.
- **Mixed** (both FSD-shaped and Clean-shaped directories present) — surface as tech debt + ask user which is the target before adding new code.

## Anti-patterns

- Bidirectional imports between slices → cyclic dependency → refactor.
- A `god-feature` slice owning UI for half the page → split by user-facing capability.
- `shared/utils.ts` becoming a dumping ground → move helpers into the slice that owns the concern, or into a typed `shared/lib/<topic>/`.
- Skipping `index.ts` and importing `features/cart/model/store.ts` directly → broken public API contract.

## Sources

- Feature-Sliced Design — https://feature-sliced.design
- FSD official examples — https://github.com/feature-sliced/examples
