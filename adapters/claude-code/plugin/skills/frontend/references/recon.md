# Stack discovery

Run:

```bash
node "${CLAUDE_SKILL_DIR}/scripts/recon.js" <package-root>
```

The report is evidence for routing, not a decision engine. Dependency values
are declared `package.json` specifiers, not proof of the installed resolution.
Each root-level TypeScript config is reported separately; an absent flag is
`null` because it may be inherited or belong to a referenced config. Confirm
installed versions and the active path from the lockfile, imports, providers,
route configuration, extended or referenced configuration, framework file
conventions, and the task's files. The script performs no network access and
does not install tooling.

When the script is unavailable, inspect:

- nearest `package.json`, lockfile, workspace definition, and package manager;
- React, TypeScript, Vite or Next.js versions and the server/client boundary;
- router, server-state and client-state libraries, forms, validation, styling, and UI primitives;
- PWA, IndexedDB, realtime, editors, Markdown, tables, charts, file generation, and browser APIs;
- native test runner, component tests, and browser tests;
- package-specific scripts used for focused checks.

Do not ask merely because several technologies coexist. A repository may intentionally contain several apps, providers, migration paths, or specialized libraries. Escalate only an unresolved choice that changes product behavior or infrastructure.
