---
name: mainframe-rust
description: Develop, debug, or review Rust crates, libraries, CLIs, services, and workers, including Cargo workspaces, async Rust, and FFI.
---

# Rust engineering

Identify the owning Cargo package and the actual binary, library, worker, or
test target. Read the crate manifest, inherited workspace settings,
`rust-toolchain.toml` when present, and the relevant CI command. Preserve the
edition, minimum supported Rust version, feature defaults, target platforms,
dependency constraints, and public API. Check which feature and target
actually exercises the edited path.

## Keep failure and ownership visible

- Propagate fallible I/O, parsing, and configuration as `Result` with causal
  context. Use panics only for proven invariants. Treat `let _ =` on a
  `Result` or task handle as a decision to verify. Dropping a Tokio
  `JoinHandle` detaches the task. Give background work an owner, a shutdown
  path, and observable failure.
- Keep synchronous I/O and substantial CPU work off the async executor.
  Bound blocking work and queues. Keep locks and transactions short and
  ensure a guard cannot block unrelated work across an `.await`.
- For FFI or `unsafe`, state the caller and memory invariants beside the
  operation. Keep validation and ownership at the boundary and exercise the
  relevant target. Preserve compatibility with existing callers and data.

## Verify the owning target

Use `mainframe-testing` for behavior changes. Start with the project's
focused test and `cargo check` or Clippy for the owning target and features.
Preserve the configured toolchain and lint flags. Use the package's existing
locked dependency route where applicable. Cargo checks can compile build
scripts and procedural macros. Keep broad target and feature matrices in CI.
Run the actual CLI or service path when behavior depends on its wiring.

For hot paths, measure the same workload and outputs before and after.
Check allocations, blocking time, and throughput where the change affects
them. For async workers, verify an applicable failure or cancellation path
and that owned tasks and resources are released.

Use [The Cargo Book](https://doc.rust-lang.org/cargo/) for manifest and
feature behavior, the [Rust Reference](https://doc.rust-lang.org/reference/)
for language rules, and the [Tokio documentation](https://docs.rs/tokio/)
for runtime and task semantics.
