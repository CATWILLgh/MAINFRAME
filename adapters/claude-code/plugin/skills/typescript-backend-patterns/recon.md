# Stack discovery

Run:

```bash
node ~/.claude/skills/mainframe/skills/typescript-backend-patterns/recon.js <package-root>
```

The report is evidence for routing, not a decision engine. Dependency values
are declared `package.json` specifiers, not proof of the installed resolution.
An absent TypeScript flag is reported as `null`, because it may be inherited.
Confirm installed versions and the active path from the lockfile, imports,
framework entrypoints, extended configuration, workspace scripts, and the
task's files.

When the script is unavailable, inspect:

- nearest `package.json`, lockfile, workspace definition, and package manager;
- Node and TypeScript constraints plus `tsconfig` module and strictness options;
- server framework and Next.js router/runtime when present;
- ORM or query client, PostgreSQL driver, migrations, validation and auth;
- queues, schedulers, realtime, storage, logging, telemetry, and tests;
- package-specific scripts used for focused checks.

Do not ask merely because several technologies coexist. A repository may intentionally contain several apps, migration paths, test levels, or adapters. Escalate only an unresolved choice that changes product behavior or infrastructure.
