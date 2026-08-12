# Runtime and package boundaries

- Work from the nearest package root in a monorepo. Use its package manager and scripts; do not infer commands from another workspace package.
- Read a package script before executing it. Lifecycle hooks and commands named
  `lint`, `format`, `test`, or `build` may rewrite files, start dependencies,
  consume credentials, or target an external environment; the name is not a
  safety contract.
- Preserve the installed Node.js and TypeScript major for established code. For new components, choose a supported Node.js LTS line and a TypeScript version supported by the framework and toolchain.
- Read `package.json`, `tsconfig`, framework compiler config, and the actual entrypoint before changing ESM/CommonJS or module resolution. A module-format migration is a project change, not incidental cleanup.
- Prefer strict types for new code. In a partially strict codebase, do not turn on global strictness as a side effect; improve the changed boundary without suppression casts.
- Do not assume browser APIs, Node APIs, or native modules are available across Node, serverless, and edge runtimes. Confirm the active runtime.
- Keep generated files, build output, and package-manager artifacts under the project's existing ownership.

Sources:
- Node.js releases — https://nodejs.org/en/about/previous-releases
- TypeScript configuration — https://www.typescriptlang.org/tsconfig/
