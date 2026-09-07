# Stack reconnaissance

Run the bundled read-only helper against the nearest affected package root:

```bash
node <skill-path>/scripts/recon.mjs <package-root>
```

Pass the package root explicitly. The helper does not search the repository for a package, execute package scripts, inspect environment variables, read secret files, access the network, or write files. It reads a bounded set of package metadata and walks only ancestor directories needed to locate the nearest repository boundary and package-manager lockfile.

Treat its JSON as routing evidence. Dependency values are declared package specifiers, not proof of installed resolution or active use. Direct compiler options may be inherited or overridden. Directory presence is not proof that a router or entrypoint is active.

Confirm relevant findings through the lockfile, installed-package metadata, imports, entrypoints, registration, extended TypeScript configuration, workspace configuration, and affected code.

When the helper is unavailable, inspect only what the task needs:

- the nearest `package.json`, workspace owner, lockfile, and package manager;
- supported Node.js and TypeScript versions, module format, and compiler configuration;
- server framework, entrypoints, runtime target, and Next.js router when present;
- persistence, migrations, runtime validation, authentication, queues, realtime, storage, caching, and observability used by the affected path;
- package-native scripts and test configuration relevant to the change.

Do not treat multiple detected technologies as a conflict. Determine which one owns the affected runtime path.
