# Reconnaissance

Start at the nearest directory containing the owning `go.mod`; account for an
effective `go.work` above it. Read manifests and existing project instructions
before running package commands. Inspect only the commands, packages, generated
owners, configuration, and tests relevant to the behavior.

Use `go env GOMOD GOWORK GOVERSION GOOS GOARCH` from the intended package root
when the selected module or toolchain is unclear. This reads Go configuration;
it does not prove the process command, build tags, runtime environment,
dependency wiring, or deployed binary. Use `go list` only at the bounded package
scope needed for the task and avoid commands that download or rewrite modules
unless that effect is in scope.

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
