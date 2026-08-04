# TypeScript discipline (backend)

`tsconfig.json` is the contract that distinguishes maintainable TS from JavaScript-with-decorations. Backend code that drifts on strictness becomes runtime-error territory.

## `strict: true` is the floor

Per TypeScript docs: "The `strict` flag enables a wide range of type checking behavior that results in stronger guarantees of program correctness".

`strict: true` enables 11 flags simultaneously, most critical being `strictNullChecks` (no `T | undefined` confusion) and `noImplicitAny` (forces explicit types where inference fails). **`strict: true` is not optional in enterprise code.** If a project's tsconfig has `strict: false`, that is technical debt — surface via `surface-ticket`, do not silently work around it.

## High-value flags NOT in `strict`

| Flag | Why valuable for backend |
|---|---|
| `noUncheckedIndexedAccess` | Array / object index access returns `T \| undefined` instead of `T`. Catches `users[0].name` when `users` could be empty. Major source of runtime crashes in service code. |
| `exactOptionalPropertyTypes` | `foo?: string` cannot be `null` (must be omitted or string). Prevents the "explicit `undefined` vs omitted" confusion in optional fields. |
| `noFallthroughCasesInSwitch` | Catches missing `break` in switch cases — classic state-machine bug. |
| `noImplicitOverride` | Forces `override` keyword on subclass methods — catches typos / signature drift. |

Recommend enabling all four for backend projects. Front-end can be more lenient on `noUncheckedIndexedAccess` due to DOM API noise.

## Module resolution

- `"module": "NodeNext"` + `"moduleResolution": "NodeNext"` for modern Node ESM projects. Explicit `.js` import extensions required.
- `"module": "CommonJS"` for legacy / NestJS projects — `.ts` imports without extension.
- Mixing strategies in one repo → frequent build errors. Pick one per package.

## Anti-patterns to flag

- `any` — explicit escape hatch. Surfaces via `# noqa`-equivalent comments — banned per `no-suppression-markers` discipline. If genuinely needed (rare — usually means modelling is wrong), surface via `surface-ticket`.
- `as` cast without runtime validation at trust boundary — type assertion lies to the compiler. Validation must accompany cast.
- `@ts-ignore` / `@ts-expect-error` — silenced check, banned per umbrella `AGENTS.md`.

## Sources

- TypeScript tsconfig reference — https://www.typescriptlang.org/tsconfig/#strict
