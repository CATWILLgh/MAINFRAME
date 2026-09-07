# Reconnaissance

Run `node scripts/recon.mjs <package-root>` with the explicit root of the frontend package being changed. Do not point it at a home directory or an entire unrelated monorepo.

The helper reads only `package.json`, conventional root-level configuration markers, fixed framework directory hints, and the nearest lockfile up to the repository boundary. It does not execute package scripts, read environment variables, use the network, scan source recursively, or write files.

Its JSON report contains sanitized declared signals. It intentionally omits dependency versions and sources, package-script bodies, URLs, arbitrary component configuration values, and source contents. Treat malformed manifests as failures and every evidence-limit entry as unresolved.

After recon, inspect imports, providers, routes, configuration, component source, call sites, tests, and the running surface relevant to the task. Directory and dependency presence do not prove the active renderer, route, component system, or browser behavior.

When the helper is unavailable, inspect the nearest package manifest and lockfile, React and framework versions, renderer and router, state and data libraries, validation and styling, installed primitives, browser capabilities, and focused test commands manually.
