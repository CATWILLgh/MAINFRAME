# Runtime and packaging

Work from the owning module, not automatically the repository root. Inspect
`go.mod`, the effective `go.work`, `toolchain` and `go` directives, vendoring,
`replace` or `exclude` entries, build tags, embedded assets, generated sources,
and the real build or process command. Preserve the established module and
workspace topology.

Keep package direction and visibility coherent. Avoid import cycles, dumping
unrelated behavior into a shared package, or widening an interface solely to
fit a test. Define interfaces at a consumer boundary when substitution is
useful; do not create one for every concrete type. Preserve zero-value and
nil semantics that callers rely on.

Treat `//go:generate`, protobuf/OpenAPI clients, mocks, SQL generators, and
embedded migrations as ownership signals. Change the canonical input and use
the project's generator when regeneration is in scope. Do not hand-edit derived
files or upgrade generators and their output as incidental cleanup.

Use the project's existing formatting, linting, vetting, static analysis, and
test commands. `gofmt` is required for changed Go source; use `goimports` only
when the project already owns that convention. Do not run `go mod tidy`, vendor
rewrites, broad dependency upgrades, or workspace changes unless the resulting
module-graph mutation belongs to the task.

Account for CGO, OS/architecture files, signal handling, and static/dynamic
linking when they affect the changed behavior. A local `go test` result does not
prove another target, container image, process supervisor, or deployed binary.
