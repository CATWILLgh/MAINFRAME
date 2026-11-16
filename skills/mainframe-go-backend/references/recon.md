# Reconnaissance

Start at the nearest directory containing the owning `go.mod`; account for an
effective `go.work` above it. Read manifests and existing project instructions
before running package commands. Inspect only the commands, packages, generated
owners, configuration, and tests relevant to the behavior.

When module or toolchain selection is unclear, inspect manifests and existing
toolchain configuration first. Use process-scoped
`GOTOOLCHAIN=local go env GOMOD GOWORK GOVERSION GOOS GOARCH` from the package
root for discovery without automatic toolchain downloads. This observes the
bundled toolchain, not the normally selected or deployed version, process wiring,
or build tags. If it cannot handle the project's required version, report the
mismatch and continue static inspection rather than installing implicitly.
Keep `go list` bounded and avoid module downloads or rewrites unless authorized.
See the official [toolchain selection contract](https://go.dev/doc/toolchain#select).

Trace from the actual `cmd/...` entrypoint, service constructor, router or
worker registration, and process command into the affected package. Locate
interfaces with both their implementations and construction sites. Check build
constraints, generated-file headers, `replace` directives, embedded files, and
platform-specific variants before choosing an owner.

For data or integration behavior, identify the concrete driver/client,
transaction owner, timeout source, retry layer, and focused test infrastructure.
For concurrency behavior, identify every goroutine and scarce resource retained
across the operation. Continue manually when evidence is ambiguous rather than
inferring ownership from directory names.
