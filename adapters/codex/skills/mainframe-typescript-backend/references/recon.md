# Stack discovery

Run the bundled script against the nearest affected package root:

```bash
node <skill-path>/scripts/recon.js <package-root>
```

Treat its report as routing evidence, not a decision engine. Dependency values
are declared `package.json` specifiers, not proof of installed resolutions. A
missing TypeScript flag is `null` because it may be inherited. Confirm installed
versions and the active path from the lockfile, imports, entrypoints, extended
configuration, workspace scripts, and affected files.

When the script is unavailable, inspect:

- nearest `package.json`, lockfile, workspace definition, and package manager;
- Node and TypeScript constraints plus module and strictness settings;
- server framework and Next.js router/runtime when present;
- ORM or query client, PostgreSQL driver, migrations, validation, and auth;
- queues, schedulers, realtime, storage, logging, telemetry, and tests;
- package-specific scripts used for focused checks.

Do not ask merely because several technologies coexist. Escalate only an
unresolved choice that changes product behavior or infrastructure.
