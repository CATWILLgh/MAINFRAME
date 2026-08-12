# Python package recon

Run the deterministic local inspection first:

```bash
python3 <skill-root>/recon.py <package-root>
```

It reads common manifests and lockfiles without importing the application, installing packages, or using the network. It reports every detected framework or library instead of silently selecting the first one.

Then establish runtime ownership from direct evidence:

1. Read the actual entrypoint and framework configuration.
2. Trace imports for the changed route, worker, command, or service.
3. Read the active dependency lock entry to establish the installed version.
4. Inspect database/session construction, middleware, validation, and tests on the affected path.
5. Detect tenant behavior from schemas, policies, and request or task context; a package manifest cannot prove it.

`none` means the manifest did not expose the signal, not that the capability is absent. A `+`-joined value means multiple packages were found. Multiple packages are normal in migrations, monorepos, test tooling, and transitional systems; determine which one owns the active path before treating the combination as a conflict.

Use manual inspection when the project relies on `setup.py`, custom requirement includes, workspace-level dependency injection, generated environments, or another layout the script does not parse. Ask the caller only when code and runtime evidence still leave a choice that changes product behavior or infrastructure.
