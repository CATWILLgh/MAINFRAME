# Reliable and economical CI

## Establish the verification contract

Use the existing project verification map from [the shared strategy](strategy.md); reconcile its CI routes rather than creating a separate inventory. Map each material guarantee to an actual test/job, supported platform/version, trigger, runner and required result. Preserve existing project-required checks and their names unless an authorized migration also updates branch/ruleset protection. Repository YAML alone does not prove server-side merge requirements. Missing access to those settings is a reported verification gap, not permission to assume enforcement.

Separate fast validation, correct-engine integration, build/package checks, security/compatibility checks and deliberately scheduled expensive work where that improves feedback or cost. Required change risks must run before acceptance; do not move essential regression protection to an optional nightly job merely to make pull requests fast. Schedule exploratory performance, extended combinations or long-running resilience tests only when their acceptance role allows it. Do not introduce every possible scanner or platform without an actual supported guarantee.

## Trigger and result correctness

Inspect PR/MR, branch, default-branch, tag, manual, scheduled and merge-queue/train behavior as applicable. Prevent duplicate equivalent pipelines without dropping required coverage. Path filtering must include shared libraries, lockfiles, test configuration, generated inputs and CI changes; when affected-scope detection is uncertain, run the needed checks.

A required check must not succeed merely because work was skipped, canceled, empty, unavailable or allowed to fail. Distinguish deliberate non-applicability, with explicit evidence, from missing execution. For conditional job graphs use a stable required gate that knows the expected jobs for the change and rejects missing/failed/canceled required results. Verify platform-specific skipped-job semantics rather than assuming a green badge proves all dependencies ran.

Check test collection and subprocess exit propagation. JUnit/coverage reports aid diagnosis; uploading them does not run tests or establish a passing suite. Do not hide failures behind `|| true`, unconditional success, allowed-failure flags, shell pipelines that lose exit codes, or success-only artifact upload.

## Speed without changing the guarantee

Use a measured job graph. Parallelize independent jobs and shard long suites with isolated fixtures, disjoint test membership and bounded runner/database concurrency. Account for queue time, dependency setup and total compute, not only one job's duration. Use fail-fast deliberately: stopping siblings speeds routine feedback but may lose compatibility diagnostics.

Cache reproducible dependencies keyed by relevant lockfiles, OS, architecture and toolchain. A cache is an optimization, not a required source of correctness; a miss must work, and a hit must not bypass validation. Partition trust boundaries and avoid secrets in caches. Use explicit artifacts for outputs consumed by downstream jobs, with producer identity, exact revision and relevant platform, expiry and failure-time diagnostics. Never treat a cache as release provenance.

Cancel superseded test runs when safe; do not interrupt deployment, data migration or a publication operation midway simply because a newer commit exists. Serialize shared-state mutations with the host's appropriate control. Keep bounded timeouts and cleanup. Retry only classified transient infrastructure failures, with bounded attempts; test assertions failing repeatedly are not green results. Quarantined flaky coverage needs an owner, tracked repair and explicit acceptance consequences.

## Trust boundaries

Untrusted contributions must not receive privileged tokens, production credentials, writable deployment environments or persistent trusted runner state. Minimize job permissions, separate test and publish/deploy identities, and use short-lived identity where supported. Review externally supplied actions/includes/images; use immutable verified references with a maintained update path when supported. Do not hard-code invented SHAs or disable all updates through abandoned pins.

Do not interpolate untrusted event text into executable shell source. Treat downloaded artifacts and caches as input from their producing trust boundary. Publication/deployment steps, external CI execution and server-side protection changes require their own authority; editing a workflow does not authorize them.

## Verify the pipeline itself

Use the host's applicable validator and project tooling when available. Test the rendered/merged configuration and event/rules graph, not YAML parsing alone. Review expected jobs for representative changed files and events, including forks, skipped jobs, failure, cancellation and absent artifacts. Use authorized runs to observe the exact revision, event, tested merge/head commit, job membership, checks and retained artifacts. A green old run or a run for another event is insufficient.

If a real run or branch-protection observation is unavailable, report what was statically checked and what remains pending. Do not claim CI is operational merely from a linter or synthetic fixture. Preserve native GitHub/GitLab differences through their focused references instead of a universal YAML template.
