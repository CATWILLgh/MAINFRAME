# Reconnaissance

Run `python3 scripts/recon.py <package-root>` with the explicit root of the Python package being changed. Do not point it at a home directory or an entire unrelated monorepo.

The helper reads only a bounded set of manifests and conventional root-level paths. It does not import application code, execute modules or package commands, inspect environment variables, use the network, or write files. Its JSON report exposes sanitized declared signals and its own evidence limits; it cannot prove imports, runtime wiring, installed versions, effective configuration, generated ownership, or behavior.

Treat `status: invalid` as a real manifest failure. Treat `status: partial` and every limitation as unresolved evidence, especially when the interpreter lacks `tomllib`. Do not install a parser merely to run reconnaissance. Continue manually from the owning project's existing tooling if needed.

After recon, inspect the relevant entrypoint, imports, registration, configuration, implementation, callers, and focused tests. When several stacks appear, identify the one that actually owns the affected path instead of treating coexistence as a conflict.

If the helper recognizes no manifest, verify that the supplied root is correct. Legacy `setup.py`, `setup.cfg`, Pipfile, and requirements files may establish a package even without `pyproject.toml`, but their presence still does not establish runtime ownership.
