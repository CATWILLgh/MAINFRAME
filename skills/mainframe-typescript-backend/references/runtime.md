# Runtime and package boundaries

- Work from the nearest package that owns the affected behavior. In a monorepo, preserve its package manager, workspace relationships, scripts, and build ownership rather than borrowing commands from another package.
- Read a package script and its lifecycle hooks before execution. Names such as `test`, `lint`, `format`, `build`, `migrate`, and `verify` do not prove that the command is read-only, local, bounded, or credential-free.
- Preserve the established Node.js and TypeScript versions unless an upgrade is assigned. For a new component, select a currently supported runtime compatible with the chosen dependencies and operating environment.
- Read `package.json`, effective TypeScript configuration, framework compiler settings, exports, and the actual entrypoint before changing ESM, CommonJS, module resolution, or emitted layout. Treat a module-system migration as a distinct compatibility change.
- `.mjs`, `.cjs`, and the nearest `package.json` `type` field have runtime meaning. TypeScript source syntax alone does not establish how Node will load emitted code.
- Prefer strong types at new and changed boundaries. In partially strict code, improve the owned boundary without enabling repository-wide strictness or hiding uncertainty behind broad casts and suppressions.
- Confirm whether the active target is a long-lived Node process, serverless function, edge runtime, worker, or bundled artifact before selecting APIs and lifecycle assumptions.
- Preserve ownership of generated files, declarations, source maps, build output, and package-manager artifacts. Change their source owner rather than editing generated copies.

Current owning references: [Node.js releases](https://nodejs.org/en/about/previous-releases), [Node.js packages](https://nodejs.org/api/packages.html), and [TypeScript TSConfig](https://www.typescriptlang.org/tsconfig/).
