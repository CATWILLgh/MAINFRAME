# Runtime and package boundaries

- Work from the nearest package root in a monorepo. Use its package manager and
  scripts; do not infer commands from another package.
- Read a package script before executing it. Lifecycle hooks and commands named
  `lint`, `format`, `test`, or `build` may rewrite files, start dependencies,
  consume credentials, or reach an external environment.
- Preserve installed Node.js and TypeScript majors in established code. For new
  components, choose a supported Node.js LTS line and framework-compatible
  TypeScript version.
- Read `package.json`, `tsconfig`, framework compiler configuration, and the
  real entrypoint before changing ESM, CommonJS, or module resolution. Treat a
  module migration as a project decision.
- Prefer strict types for new code. In a partially strict codebase, improve the
  changed boundary without global strictness changes or suppression casts.
- Confirm whether the active environment is Node, serverless, or edge before
  using browser APIs, Node APIs, or native modules.
- Preserve ownership of generated files, build output, and package-manager
  artifacts.

Sources: [Node.js releases](https://nodejs.org/en/about/previous-releases),
[TypeScript configuration](https://www.typescriptlang.org/tsconfig/).
